# Root Cause Analysis & Instrumentation

## Executive Summary

**Problem**: Batch processing completes in 5-8 seconds with all 24 files marked as FAILED.

**Root Cause**: Unknown - requires instrumentation to diagnose.

**Architecture Discovery**: This system does **NOT use Redis queues**. It makes direct synchronous HTTP calls from Node.js orchestrator to Python worker API.

## Changes Applied

### 1. Orchestrator Logging (`src/services/orchestrator.js`)

**Added:**
- Batch start/completion logging
- File-by-file processing logs with timing
- Worker HTTP error details (status codes, response data)
- Success/failure counts
- Extraction status tracking

**Lines changed:** 92-141 (entire `processBatch` function)

**Purpose:** Trace every step of batch processing to identify where failures occur.

### 2. ZIP Extractor Logging (`src/services/zipExtractor.js`)

**Added:**
- ZIP extraction path logging
- List of all files found (supported and unsupported)
- file_extractions creation confirmation
- Run ID tracking

**Lines changed:** 13-101 (entire `extractBatch` function)

**Purpose:** Verify files are actually extracted and DB records are created correctly.

### 3. Worker Client Error Handling (`src/services/workerClient.js`)

**Added:**
- Detailed HTTP error logging
- Network error detection (ECONNREFUSED = worker not running)
- Response status and data logging
- Distinguishes between network errors vs. processing errors

**Lines changed:** 14-52 (all three methods)

**Purpose:** Identify if worker is unreachable or returning errors.

## Files Changed

```
src/services/orchestrator.js     - Enhanced logging for batch processing
src/services/zipExtractor.js     - Enhanced logging for file extraction
src/services/workerClient.js     - Enhanced error handling for HTTP calls
```

**No schema changes. No breaking changes. Only adds logging.**

## How to Apply

### Step 1: Restart Backend

```powershell
# Stop backend (Ctrl+C in terminal)

# Start with new code
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
npm start
```

**Expected:**
```
✅ Database connectivity verified on startup
Backend running on port 3001
```

### Step 2: Verify Worker is Running

```powershell
# Check worker health
Invoke-RestMethod http://localhost:8000/health
```

**Expected:**
```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "llm_status": "ok",
    "parsers_ready": true
  }
}
```

**If worker not running or shows errors:**
```powershell
# Check openai version
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend\workers
pip show openai
# Should show Version: 1.30.0 or higher

# If still 1.10.0:
pip install --upgrade openai

# Restart worker
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
uvicorn workers.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3: Test with Small Batch

```powershell
# Upload test ZIP (2-3 PDFs)
$upload = Invoke-RestMethod `
  -Method POST `
  -Uri http://localhost:3001/upload-tender `
  -Form @{file=Get-Item "test.zip"}

$batchId = $upload.batch_id
Write-Host "Batch ID: $batchId"

# Trigger processing
Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:3001/api/batches/$batchId/process" `
  -ContentType "application/json" `
  -Body '{"concurrency":2}'
```

### Step 4: Monitor BOTH Terminals

**Backend terminal** will show:
```
[Orchestrator] Starting batch batch_...
[ZipExtractor] Starting extraction...
[ZipExtractor] Found X files...
[Orchestrator] → Processing file: ...
[Orchestrator] ✓ File ... completed in Xms
```

**Worker terminal** will show:
```
Processing file: C:\Users\...\file.pdf
Parsed 12345 characters...
Successfully processed ...
INFO: "POST /process-file HTTP/1.1" 200 OK
```

### Step 5: Check Status

```powershell
# Poll status every 10 seconds
Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/status"
```

**Expected:**
- `files_pending` decreases
- `files_success` increases
- Processing takes 5-30 minutes (NOT 5 seconds)

**If fails:**
```powershell
# Get errors
Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/errors"
```

## Diagnostic Checklist

Based on logs, identify which scenario matches:

### ✅ Scenario 1: Worker Not Running
**Backend logs:**
```
[WorkerClient] processFile failed for ...:
  Code: ECONNREFUSED (Worker not reachable)
```
**Fix:** Start worker with `uvicorn workers.api.main:app --host 0.0.0.0 --port 8000 --reload`

### ✅ Scenario 2: Worker Returns 500 (Processing Error)
**Backend logs:**
```
[WorkerClient] processFile failed for ...:
  Status: 500
  Data: {"detail":"...error message..."}
```
**Fix:** Check worker logs for the actual error. Common causes:
- File not found (check extracted files exist)
- OpenAI client initialization failed (upgrade package + restart)
- Parsing error (corrupt PDF)

### ✅ Scenario 3: Files Process But Mark as FAILED
**Backend logs:**
```
[Orchestrator] ✓ File ... completed in 234ms  # Very fast = suspicious
```
**Worker logs:**
```
Processing file: ...
Failed to process ...: [error message]
INFO: "POST /process-file HTTP/1.1" 200 OK  # Returns 200 but DB marked as failed
```
**Fix:** Worker is catching errors and marking files as failed. Check errors endpoint to see actual error message.

### ✅ Scenario 4: No Files Found After Extraction
**Backend logs:**
```
[ZipExtractor] 24 supported files found
[Orchestrator] Found 0 files to process
```
**Fix:** Run ID mismatch. Check DB:
```sql
SELECT batch_id, run_id FROM processing_jobs WHERE batch_id = '...';
SELECT run_id, status FROM file_extractions WHERE run_id = '...';
```

## Expected Behavior After Fix

**Healthy processing:**
1. Upload completes instantly
2. Processing triggered, returns 202
3. Backend logs show extraction (1-3 seconds)
4. Backend logs show file processing starting
5. Worker logs show each file being processed (10-60 seconds each)
6. Files transition: pending → processing → SUCCESS
7. Batch completes after 5-30 minutes (NOT 5 seconds)
8. Status shows files_success > 0

**Timeline:**
- Extraction: 1-3 seconds
- Per-file processing: 10-60 seconds
- Total (24 files, concurrency=2): 5-30 minutes
- Aggregation: 1-2 seconds

**Red flag:**
- **If batch completes in < 10 seconds → Something is broken**
- **All files FAILED → Check errors endpoint for actual error**
- **No logs in worker → Worker not receiving requests**

## Next Steps

1. **Apply changes** (restart backend)
2. **Test with small batch** (2-3 files)
3. **Watch logs in BOTH terminals**
4. **Report findings**:
   - Copy backend logs from [Orchestrator] lines
   - Copy worker logs
   - Copy status endpoint output
   - Copy errors endpoint output (if files fail)

The logs will reveal the exact point of failure.

## Notes

- **Redis is NOT used** - despite being mentioned, this codebase doesn't use queues
- **HTTP calls are synchronous** - orchestrator waits for each worker response
- **Concurrency is manual** - using Promise.all() with N workers, not a queue
- **No job persistence** - if backend crashes mid-processing, jobs are lost
- **Worker must be accessible** at http://localhost:8000 or WORKER_API_URL
