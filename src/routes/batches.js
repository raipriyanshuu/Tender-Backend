import express from "express";
import { query } from "../db.js";
import { processBatch } from "../services/orchestrator.js";
import { processRateLimiter } from "../middleware/rateLimiter.js";

const router = express.Router();

router.post("/api/batches/:batchId/process", processRateLimiter, async (req, res) => {
  const { batchId } = req.params;
  const concurrency = Number(req.body?.concurrency || process.env.WORKER_CONCURRENCY || 3);

  processBatch(batchId, concurrency).catch((err) => {
    console.error(`Batch processing failed for ${batchId}:`, err.message);
  });

  res.status(202).json({
    success: true,
    message: `Processing started for batch ${batchId}`,
    batch_id: batchId,
  });
});

router.get("/api/batches/:batchId/status", async (req, res) => {
  const { batchId } = req.params;
  const result = await query(
    "SELECT * FROM batch_status_summary WHERE batch_id = $1",
    [batchId]
  );
  const row = result.rows[0];
  if (!row) {
    return res.status(404).json({ error: "Batch not found" });
  }
  res.json(row);
});

router.get("/api/batches/:batchId/files", async (req, res) => {
  const { batchId } = req.params;
  const job = await query(
    "SELECT run_id, batch_id FROM processing_jobs WHERE batch_id = $1",
    [batchId]
  );
  if (!job.rows[0]) {
    return res.status(404).json({ error: "Batch not found" });
  }
  const runId = job.rows[0].run_id || job.rows[0].batch_id;
  const files = await query(
    "SELECT * FROM file_extractions WHERE run_id = $1 ORDER BY created_at ASC",
    [runId]
  );
  res.json({ batch_id: batchId, files: files.rows });
});

router.get("/api/batches/:batchId/summary", async (req, res) => {
  const { batchId } = req.params;

  // Get batch info
  const job = await query(
    "SELECT run_id, batch_id, status FROM processing_jobs WHERE batch_id = $1",
    [batchId]
  );
  if (!job.rows[0]) {
    return res.status(404).json({ error: "Batch not found" });
  }

  const runId = job.rows[0].run_id || job.rows[0].batch_id;

  // Try to get existing summary
  const summary = await query(
    "SELECT * FROM run_summaries WHERE run_id IN ($1, $2) ORDER BY created_at DESC LIMIT 1",
    [runId, job.rows[0].batch_id]
  );

  if (summary.rows[0]) {
    return res.json({
      success: true,
      data: summary.rows[0]
    });
  }

  // ON-DEMAND AGGREGATION: If summary missing but batch is done, trigger aggregation
  console.log(`[Batches] Summary not found for batch ${batchId}, checking if batch is complete`);

  const status = await query(
    "SELECT * FROM batch_status_summary WHERE batch_id = $1",
    [batchId]
  );

  if (!status.rows[0]) {
    return res.status(404).json({ error: "Summary not found" });
  }

  const batchStatus = status.rows[0];
  const filesSuccess = parseInt(batchStatus.files_success || 0);
  const filesFailed = parseInt(batchStatus.files_failed || 0);
  const filesProcessing = parseInt(batchStatus.files_processing || 0);
  const filesPending = parseInt(batchStatus.files_pending || 0);
  const totalFiles = parseInt(batchStatus.total_files || 0);

  console.log(`[Batches] Batch ${batchId} status:`, {
    filesSuccess,
    filesFailed,
    filesProcessing,
    filesPending,
    totalFiles,
    sum: filesSuccess + filesFailed
  });

  // If batch is complete but summary is missing, trigger on-demand aggregation
  if (
    totalFiles > 0 &&
    filesProcessing === 0 &&
    filesPending === 0 &&
    (filesSuccess + filesFailed) >= totalFiles
  ) {
    console.log(`[Batches] Batch ${batchId} is complete but summary is missing - triggering on-demand aggregation`);

    try {
      // Update batch status to completed if still in processing
      if (job.rows[0].status === "processing") {
        const finalStatus = filesFailed > 0 ? "completed_with_errors" : "completed";
        console.log(`[Batches] Updating batch ${batchId} status from processing to ${finalStatus}`);

        await query(
          `UPDATE processing_jobs 
           SET status = $2, completed_at = NOW(), updated_at = NOW() 
           WHERE batch_id = $1`,
          [batchId, finalStatus]
        );
      }

      // Enqueue aggregate job
      const { enqueueAggregateJob } = await import("../services/queueClient.js");
      await enqueueAggregateJob(batchId);

      console.log(`[Batches] Aggregate job enqueued for batch ${batchId}`);

      // Return 202 Accepted to indicate summary is being generated
      return res.status(202).json({
        message: "Summary is being generated. Please retry in a few seconds.",
        batch_id: batchId,
        retry_after: 5
      });
    } catch (err) {
      console.error(`[Batches] Failed to enqueue aggregate job for ${batchId}:`, err);
      return res.status(500).json({ error: "Failed to trigger summary generation" });
    }
  }

  // Batch is not complete yet or in unexpected state
  return res.status(404).json({
    error: "Summary not found",
    hint: "Batch may still be processing"
  });
});

router.get("/api/batches/:batchId/errors", async (req, res) => {
  const { batchId } = req.params;
  const job = await query(
    "SELECT run_id, batch_id FROM processing_jobs WHERE batch_id = $1",
    [batchId]
  );
  if (!job.rows[0]) {
    return res.status(404).json({ error: "Batch not found" });
  }
  const runId = job.rows[0].run_id || job.rows[0].batch_id;
  const failed = await query(
    `
      SELECT *
      FROM file_extractions
      WHERE run_id = $1 AND status = 'FAILED'
      ORDER BY processing_completed_at DESC NULLS LAST, created_at DESC
    `,
    [runId]
  );
  res.json({ batch_id: batchId, errors: failed.rows });
});

router.post("/api/batches/:batchId/retry-failed", processRateLimiter, async (req, res) => {
  const { batchId } = req.params;
  const concurrency = Number(req.body?.concurrency || process.env.WORKER_CONCURRENCY || 3);

  const job = await query(
    "SELECT run_id, batch_id FROM processing_jobs WHERE batch_id = $1",
    [batchId]
  );
  if (!job.rows[0]) {
    return res.status(404).json({ error: "Batch not found" });
  }
  const runId = job.rows[0].run_id || job.rows[0].batch_id;

  await query(
    `
      UPDATE file_extractions
      SET status = 'pending',
          error = NULL,
          error_type = NULL,
          processing_started_at = NULL,
          processing_completed_at = NULL,
          processing_duration_ms = NULL,
          retry_count = 0,
          updated_at = now()
      WHERE run_id = $1 AND status = 'FAILED'
    `,
    [runId]
  );

  processBatch(batchId, concurrency).catch((err) => {
    console.error(`Retry failed for ${batchId}:`, err.message);
  });

  res.status(202).json({ success: true, batch_id: batchId });
});

export default router;
