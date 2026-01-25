import express from "express";
import fs from "fs/promises";
import path from "path";
import { query } from "../db.js";
import { workerClient } from "../services/workerClient.js";
import { AlertSeverity, createAlert } from "../services/alerting.js";

const router = express.Router();

const STORAGE_BASE_PATH =
  process.env.STORAGE_BASE_PATH || path.join(process.cwd(), "shared");

async function checkDatabase() {
  const start = Date.now();
  await query("SELECT 1");
  return { status: "ok", latency_ms: Date.now() - start };
}

async function checkWorkerApi() {
  const start = Date.now();
  const data = await workerClient.healthCheck();
  return { status: data?.status || "ok", latency_ms: Date.now() - start, details: data };
}

async function checkFilesystem() {
  await fs.access(STORAGE_BASE_PATH);
  return { status: "ok", path: STORAGE_BASE_PATH };
}

async function checkRecentBatches() {
  const result = await query(
    `
      SELECT
        COUNT(*) FILTER (WHERE status = 'completed') as completed,
        COUNT(*) FILTER (WHERE status = 'completed_with_errors') as completed_with_errors,
        COUNT(*) FILTER (WHERE status = 'failed') as failed
      FROM processing_jobs
      WHERE created_at >= now() - interval '24 hours'
    `
  );
  const row = result.rows[0] || { completed: 0, completed_with_errors: 0, failed: 0 };
  const total = Number(row.completed) + Number(row.completed_with_errors) + Number(row.failed);
  const success = Number(row.completed) + Number(row.completed_with_errors);
  const successRate = total > 0 ? Math.round((success / total) * 100) : 100;
  return { status: "ok", success_rate_percent: successRate };
}

router.get("/health", async (req, res) => {
  const checks = {};
  let overallStatus = "healthy";

  try {
    checks.database = await checkDatabase();
  } catch (error) {
    checks.database = { status: "error", error: error.message };
    overallStatus = "unhealthy";
  }

  try {
    checks.worker_api = await checkWorkerApi();
    if (checks.worker_api.status !== "ok") {
      overallStatus = overallStatus === "healthy" ? "degraded" : overallStatus;
    }
  } catch (error) {
    checks.worker_api = { status: "error", error: error.message };
    overallStatus = "unhealthy";
  }

  try {
    checks.filesystem = await checkFilesystem();
  } catch (error) {
    checks.filesystem = { status: "error", error: error.message };
    overallStatus = "unhealthy";
  }

  try {
    checks.recent_batches = await checkRecentBatches();
  } catch (error) {
    checks.recent_batches = { status: "error", error: error.message };
    overallStatus = overallStatus === "healthy" ? "degraded" : overallStatus;
  }

  if (overallStatus !== "healthy" && checks.database?.status === "ok") {
    const alertType = overallStatus === "unhealthy" ? "SYSTEM_UNHEALTHY" : "SYSTEM_DEGRADED";
    await createAlert(alertType, AlertSeverity.WARNING, "Health check reported issues", checks);
  }

  res.json({
    status: overallStatus,
    timestamp: new Date().toISOString(),
    checks,
  });
});

export default router;
