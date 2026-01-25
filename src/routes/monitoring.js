import express from "express";
import fs from "fs/promises";
import path from "path";
import { query } from "../db.js";
import pool from "../db.js";

const router = express.Router();

const STORAGE_BASE_PATH =
  process.env.STORAGE_BASE_PATH || path.join(process.cwd(), "shared");

const TIME_RANGES = {
  "1h": "1 hour",
  "24h": "24 hours",
  "7d": "7 days",
};

async function getDirectorySizeBytes(targetPath) {
  let total = 0;
  const entries = await fs.readdir(targetPath, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(targetPath, entry.name);
    if (entry.isDirectory()) {
      total += await getDirectorySizeBytes(fullPath);
    } else if (entry.isFile()) {
      const stat = await fs.stat(fullPath);
      total += stat.size;
    }
  }
  return total;
}

router.get("/api/monitoring/errors", async (req, res) => {
  const timeRangeKey = req.query.time_range || "24h";
  const timeRange = TIME_RANGES[timeRangeKey] || TIME_RANGES["24h"];
  const errorType = req.query.error_type || null;
  const batchId = req.query.batch_id || null;

  const params = [timeRange];
  const conditions = [
    "fe.status = 'FAILED'",
    "COALESCE(fe.processing_completed_at, fe.created_at) >= now() - $1::interval",
  ];

  if (errorType) {
    params.push(errorType);
    conditions.push(`fe.error_type = $${params.length}`);
  }

  if (batchId) {
    params.push(batchId);
    conditions.push(`(pj.batch_id = $${params.length})`);
  }

  const whereClause = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";

  const summaryQuery = `
    SELECT fe.error_type, COUNT(*) as total
    FROM file_extractions fe
    LEFT JOIN processing_jobs pj ON fe.run_id = pj.batch_id OR fe.run_id = pj.run_id
    ${whereClause}
    GROUP BY fe.error_type
  `;

  const recentQuery = `
    SELECT
      pj.batch_id,
      fe.doc_id,
      fe.filename,
      fe.error_type,
      fe.error as error_message,
      fe.retry_count,
      COALESCE(fe.processing_completed_at, fe.created_at) as timestamp
    FROM file_extractions fe
    LEFT JOIN processing_jobs pj ON fe.run_id = pj.batch_id OR fe.run_id = pj.run_id
    ${whereClause}
    ORDER BY timestamp DESC
    LIMIT 20
  `;

  const [summaryResult, recentResult] = await Promise.all([
    query(summaryQuery, params),
    query(recentQuery, params),
  ]);

  const byType = {};
  for (const row of summaryResult.rows) {
    byType[row.error_type] = Number(row.total);
  }

  res.json({
    summary: {
      total_errors: summaryResult.rows.reduce((sum, row) => sum + Number(row.total), 0),
      by_type: byType,
      batches_affected: new Set(recentResult.rows.map((row) => row.batch_id).filter(Boolean)).size,
    },
    recent_errors: recentResult.rows,
  });
});

router.get("/api/monitoring/performance", async (req, res) => {
  const limit = Number(req.query.limit || 30);
  const result = await query(
    "SELECT * FROM processing_performance_metrics ORDER BY processing_date DESC LIMIT $1",
    [limit]
  );
  res.json({ metrics: result.rows });
});

router.get("/api/monitoring/database", async (req, res) => {
  const tableSizes = await query(
    `
      SELECT
        relname as table,
        pg_size_pretty(pg_total_relation_size(relid)) as size
      FROM pg_catalog.pg_statio_user_tables
      ORDER BY pg_total_relation_size(relid) DESC
      LIMIT 10
    `
  );

  res.json({
    status: "ok",
    connection_pool: {
      total: pool.totalCount,
      idle: pool.idleCount,
      waiting: pool.waitingCount,
    },
    table_sizes: tableSizes.rows,
  });
});

router.get("/api/monitoring/filesystem", async (req, res) => {
  try {
    // Calculate storage directory size (cross-platform)
    const usedBytes = await getDirectorySizeBytes(STORAGE_BASE_PATH);
    const usedMB = Math.round(usedBytes / (1024 * 1024));

    const retentionDays = Number(process.env.BATCH_RETENTION_DAYS || "30");
    const oldBatches = await query(
      `
        SELECT batch_id
        FROM processing_jobs
        WHERE completed_at IS NOT NULL
          AND completed_at < now() - $1::interval
        ORDER BY completed_at ASC
        LIMIT 20
      `,
      [`${retentionDays} days`]
    );

    res.json({
      disk_usage_mb: usedMB,
      disk_usage_bytes: usedBytes,
      storage_path: STORAGE_BASE_PATH,
      old_batches_count: oldBatches.rowCount,
      suggested_cleanup_batches: oldBatches.rows.map((row) => row.batch_id),
      note: "For full disk stats, use OS-level monitoring tools",
    });
  } catch (error) {
    res.status(500).json({ error: "Failed to read filesystem status", details: error.message });
  }
});

export default router;
