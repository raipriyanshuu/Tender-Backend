# Queue-Based Architecture Migration Plan

## Current Problem

The system uses **direct HTTP calls** instead of queues, despite Redis being available:
- Orchestrator makes synchronous HTTP calls to worker
- No job persistence if backend crashes
- No retry/failure management at infrastructure level
- Cannot scale workers independently

## Proposed Architecture

```
┌──────────┐
│  Upload  │
└────┬─────┘
     ↓
┌────────────────┐
│ Create Batch   │
│ (status=queued)│
└────┬───────────┘
     ↓
┌────────────────┐      ┌──────────────┐
│ POST /process  │─────→│ Enqueue Jobs │
│ (API endpoint) │      │ to Redis     │
└────────────────┘      └──────┬───────┘
                               ↓
                        ┌──────────────┐
                        │  Redis Queue │
                        │  (BullMQ)    │
                        └──────┬───────┘
                               ↓
                        ┌──────────────────┐
                        │ Worker Processes │
                        │ (consume queue)  │
                        └──────┬───────────┘
                               ↓
                        ┌──────────────┐
                        │ Process File │
                        │ Update DB    │
                        └──────────────┘
```

## Implementation Steps

### Step 1: Install Queue Dependencies

**Backend:**
```json
// package.json
"dependencies": {
  "bullmq": "^5.0.0",
  "ioredis": "^5.3.0"
}
```

**Worker:**
```txt
# requirements.txt
redis==5.0.1
```

### Step 2: Create Queue Service (Backend)

**src/services/queueService.js**
```javascript
import { Queue, Worker } from 'bullmq';
import IORedis from 'ioredis';

const connection = new IORedis({
  host: process.env.REDIS_HOST || 'localhost',
  port: Number(process.env.REDIS_PORT || '6379'),
  maxRetriesPerRequest: null,
});

export const fileProcessingQueue = new Queue('file-processing', { connection });

// Enqueue a file for processing
export async function enqueueFileProcessing(docId, priority = 0) {
  await fileProcessingQueue.add(
    'process-file',
    { doc_id: docId },
    {
      priority,
      attempts: 3,
      backoff: {
        type: 'exponential',
        delay: 2000,
      },
      removeOnComplete: 100,  // Keep last 100 completed
      removeOnFail: 1000,     // Keep last 1000 failed
    }
  );
  console.log(`[Queue] Enqueued file: ${docId}`);
}

// Enqueue aggregation job
export async function enqueueAggregation(batchId) {
  await fileProcessingQueue.add(
    'aggregate-batch',
    { batch_id: batchId },
    {
      priority: 100,  // High priority
      attempts: 2,
    }
  );
  console.log(`[Queue] Enqueued aggregation: ${batchId}`);
}
```

### Step 3: Update Orchestrator to Use Queue

**src/services/orchestrator.js (modified)**
```javascript
import { enqueueFileProcessing, enqueueAggregation } from './queueService.js';

export async function processBatch(batchId, concurrency = DEFAULT_CONCURRENCY) {
  console.log(`[Orchestrator] Starting batch ${batchId}`);
  
  const job = await getBatch(batchId);
  if (!job) {
    throw new Error(`Batch not found: ${batchId}`);
  }

  // Extract ZIP if needed
  if (job.status === "queued" || job.status === "pending") {
    console.log(`[Orchestrator] Extracting ZIP for batch ${batchId}...`);
    const extractResult = await extractBatch(batchId);
    console.log(`[Orchestrator] Extraction complete: ${extractResult.total_files} files`);
  }

  await updateBatchStatus(batchId, STATUSES.PROCESSING);

  const runId = resolveRunId(job);
  const files = await getBatchFiles(runId);
  
  if (files.length === 0) {
    console.warn(`[Orchestrator] No files to process for batch ${batchId}`);
    await updateBatchStatus(batchId, STATUSES.FAILED, "No files to process");
    return { batch_id: batchId, processed: 0, failed: 0 };
  }

  console.log(`[Orchestrator] Enqueuing ${files.length} files...`);
  
  // CHANGE: Enqueue jobs instead of direct HTTP calls
  for (const file of files) {
    await enqueueFileProcessing(file.doc_id);
  }

  console.log(`[Orchestrator] ${files.length} files enqueued successfully`);
  
  // Schedule aggregation job (will run after all files complete)
  await enqueueAggregation(batchId);

  return { batch_id: batchId, enqueued: files.length };
}
```

### Step 4: Create Python Queue Worker

**workers/queue_worker.py** (NEW FILE)
```python
from __future__ import annotations

import json
import sys
from redis import Redis
from workers.config import load_config
from workers.database.connection import get_session
from workers.processing.extractor import process_file
from workers.processing.aggregator import aggregate_batch

def main():
    config = load_config()
    redis_client = Redis(
        host=config.redis_host or 'localhost',
        port=config.redis_port or 6379,
        decode_responses=True
    )
    
    print(f"[QueueWorker] Connecting to Redis at {config.redis_host}:{config.redis_port}")
    print("[QueueWorker] Listening for jobs...")
    
    while True:
        try:
            # Pop job from queue (blocking, 1 second timeout)
            job_data = redis_client.brpop('bullmq:file-processing:wait', timeout=1)
            
            if not job_data:
                continue
            
            _, job_json = job_data
            job = json.loads(job_json)
            
            job_name = job.get('name')
            job_payload = job.get('data', {})
            
            print(f"[QueueWorker] Processing job: {job_name}")
            
            if job_name == 'process-file':
                doc_id = job_payload.get('doc_id')
                with get_session(config) as session:
                    process_file(session, doc_id, config)
                print(f"[QueueWorker] ✓ File {doc_id} completed")
                
            elif job_name == 'aggregate-batch':
                batch_id = job_payload.get('batch_id')
                with get_session(config) as session:
                    aggregate_batch(session, batch_id, config)
                print(f"[QueueWorker] ✓ Aggregation {batch_id} completed")
                
        except KeyboardInterrupt:
            print("\n[QueueWorker] Shutting down...")
            sys.exit(0)
        except Exception as exc:
            print(f"[QueueWorker] Error: {exc}")
            continue

if __name__ == "__main__":
    main()
```

### Step 5: Update Worker Config

**workers/config.py (add Redis settings)**
```python
@dataclass
class Config:
    # ... existing fields ...
    redis_host: str = field(default="localhost")
    redis_port: int = field(default=6379)
    
def load_config() -> Config:
    # ... existing code ...
    return Config(
        # ... existing fields ...
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
    )
```

### Step 6: Update Environment Variables

**Backend .env:**
```env
REDIS_HOST=localhost
REDIS_PORT=6379
```

**Workers .env:**
```env
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Step 7: Start Queue Worker

```powershell
# In addition to the HTTP worker
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
python -m workers.queue_worker
```

## Migration Path

### Phase 1: Dual Mode (Backwards Compatible)
- Keep HTTP endpoints working
- Add queue system in parallel
- Use environment variable to choose mode: `USE_QUEUE=true`

### Phase 2: Queue Primary
- Default to queue
- Keep HTTP endpoints for health checks only

### Phase 3: Queue Only
- Remove direct HTTP processing endpoints
- Pure queue-based architecture

## Benefits

✅ **Job Persistence**: Jobs survive backend crashes  
✅ **Retry Logic**: Built-in retry with exponential backoff  
✅ **Priority**: Critical batches can be prioritized  
✅ **Scalability**: Scale workers independently  
✅ **Monitoring**: Built-in job status tracking  
✅ **Concurrency Control**: Queue handles rate limiting  

## Verification

```powershell
# 1. Check queue length
Invoke-RestMethod http://localhost:3001/api/queue/stats

# 2. Monitor jobs
docker exec -it redis-local redis-cli
> LLEN bullmq:file-processing:wait
> LLEN bullmq:file-processing:active
```
