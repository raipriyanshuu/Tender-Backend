import { createClient } from "redis";
import crypto from "crypto";

const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379";
const REDIS_QUEUE_KEY = process.env.REDIS_QUEUE_KEY || "tender:jobs";
const REDIS_PROCESSING_KEY = `${REDIS_QUEUE_KEY}:processing`;
const REDIS_DELAYED_KEY = `${REDIS_QUEUE_KEY}:delayed`;
const REDIS_DEAD_KEY = `${REDIS_QUEUE_KEY}:dead`;
const MAX_RETRY_ATTEMPTS = Number(process.env.MAX_RETRY_ATTEMPTS || "3");
const RETRY_DELAY_MS = Number(
  process.env.QUEUE_RETRY_DELAY_MS ||
    String(Number(process.env.RETRY_BASE_DELAY_SECONDS || "2") * 1000)
);

let clientPromise = null;

async function getRedisClient() {
  if (!clientPromise) {
    const client = createClient({ url: REDIS_URL });
    client.on("error", (err) => {
      console.error("[QueueClient] Redis error:", err.message);
    });
    clientPromise = client.connect().then(() => client);
  }
  return clientPromise;
}

export async function enqueueJob(payload) {
  const client = await getRedisClient();
  const job = {
    job_id: crypto.randomUUID(),
    ...payload,
    attempt: 0,
    max_attempts: MAX_RETRY_ATTEMPTS,
    retry_delay_ms: RETRY_DELAY_MS,
    enqueued_at: new Date().toISOString(),
  };
  await client.lPush(REDIS_QUEUE_KEY, JSON.stringify(job));
  return job;
}

export async function enqueueFileJob(docId, batchId) {
  return enqueueJob({
    type: "process_file",
    doc_id: docId,
    batch_id: batchId,
  });
}

export async function enqueueAggregateJob(batchId) {
  return enqueueJob({
    type: "aggregate_batch",
    batch_id: batchId,
  });
}

export async function getQueueMetrics() {
  const client = await getRedisClient();
  const [queueLength, processingCount, delayedCount, deadCount] =
    await Promise.all([
      client.lLen(REDIS_QUEUE_KEY),
      client.sCard(REDIS_PROCESSING_KEY),
      client.zCard(REDIS_DELAYED_KEY),
      client.lLen(REDIS_DEAD_KEY),
    ]);
  return {
    queue_key: REDIS_QUEUE_KEY,
    processing_key: REDIS_PROCESSING_KEY,
    delayed_key: REDIS_DELAYED_KEY,
    dead_key: REDIS_DEAD_KEY,
    queue_length: queueLength,
    processing_count: processingCount,
    delayed_count: delayedCount,
    dead_count: deadCount,
  };
}

export {
  REDIS_QUEUE_KEY,
  REDIS_PROCESSING_KEY,
  REDIS_DELAYED_KEY,
  REDIS_DEAD_KEY,
};
