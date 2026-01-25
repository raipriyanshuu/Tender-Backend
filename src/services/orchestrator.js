import { query } from "../db.js";
import { extractBatch } from "./zipExtractor.js";
import { enqueueFileJob } from "./queueClient.js";

const MAX_RETRY_ATTEMPTS = Number(process.env.MAX_RETRY_ATTEMPTS || "3");
const DEFAULT_CONCURRENCY = Number(process.env.WORKER_CONCURRENCY || "3");

const STATUSES = {
  PENDING: "pending",
  FAILED: "failed",
  PROCESSING: "processing",
  COMPLETED: "completed",
  COMPLETED_WITH_ERRORS: "completed_with_errors",
};

function resolveRunId(job) {
  return job.run_id || job.batch_id;
}

async function getBatch(batchId) {
  const result = await query(
    "SELECT * FROM processing_jobs WHERE batch_id = $1",
    [batchId]
  );
  return result.rows[0] || null;
}

async function getBatchFiles(runId) {
  const result = await query(
    `
      SELECT *
      FROM file_extractions
      WHERE run_id = $1
        AND (
          status = $2
          OR (status = $3 AND retry_count < $4)
        )
      ORDER BY created_at ASC
    `,
    [runId, STATUSES.PENDING, STATUSES.FAILED, MAX_RETRY_ATTEMPTS]
  );
  return result.rows;
}

async function updateBatchStatus(batchId, status, errorMessage = null) {
  await query(
    `
      UPDATE processing_jobs
      SET status = $2,
          error_message = $3,
          updated_at = now()
      WHERE batch_id = $1
    `,
    [batchId, status, errorMessage]
  );
}

async function markBatchCompleted(batchId, status) {
  await query(
    `
      UPDATE processing_jobs
      SET status = $2,
          completed_at = now(),
          updated_at = now()
      WHERE batch_id = $1
    `,
    [batchId, status]
  );
}

async function runWithConcurrency(items, handler, concurrency = DEFAULT_CONCURRENCY) {
  const results = [];
  let index = 0;

  const workers = Array.from({ length: concurrency }, async () => {
    while (index < items.length) {
      const currentIndex = index;
      index += 1;
      const item = items[currentIndex];
      try {
        results[currentIndex] = await handler(item);
      } catch (error) {
        results[currentIndex] = { error };
      }
    }
  });

  await Promise.all(workers);
  return results;
}

export async function processBatch(batchId, concurrency = DEFAULT_CONCURRENCY) {
  console.log(`[Orchestrator] Starting batch ${batchId} with concurrency=${concurrency}`);
  
  const job = await getBatch(batchId);
  if (!job) {
    throw new Error(`Batch not found: ${batchId}`);
  }
  console.log(`[Orchestrator] Batch status: ${job.status}, run_id: ${job.run_id || 'null'}`);

  // Extract ZIP if status is 'queued' (first time)
  if (job.status === "queued" || job.status === "pending") {
    console.log(`[Orchestrator] Extracting ZIP for batch ${batchId}...`);
    try {
      const extractResult = await extractBatch(batchId);
      console.log(`[Orchestrator] Extraction complete: ${extractResult.total_files} files extracted`);
    } catch (error) {
      console.error(`[Orchestrator] Extraction failed for ${batchId}:`, error.message);
      throw error;
    }
  }

  await updateBatchStatus(batchId, STATUSES.PROCESSING);

  const runId = resolveRunId(job);
  console.log(`[Orchestrator] Using run_id: ${runId}`);
  
  const files = await getBatchFiles(runId);
  console.log(`[Orchestrator] Found ${files.length} files to process (pending or retryable)`);
  
  if (files.length === 0) {
    console.warn(`[Orchestrator] No files to process for batch ${batchId}`);
    await updateBatchStatus(batchId, STATUSES.FAILED, "No files to process");
    return { batch_id: batchId, processed: 0, failed: 0 };
  }

  let failed = 0;
  let succeeded = 0;

  console.log(`[Orchestrator] Enqueuing ${files.length} files for processing...`);

  await runWithConcurrency(
    files,
    async (file) => {
      console.log(`[Orchestrator] → Enqueue file: ${file.doc_id} (${file.filename})`);
      try {
        await enqueueFileJob(file.doc_id, batchId);
        succeeded += 1;
      } catch (error) {
        failed += 1;
        console.error(`[Orchestrator] ✗ Failed to enqueue ${file.doc_id}:`, error.message);
        throw error;
      }
    },
    concurrency
  );

  console.log(`[Orchestrator] Enqueue complete: ${succeeded} queued, ${failed} failed`);

  return { batch_id: batchId, enqueued: files.length, failed };
}
