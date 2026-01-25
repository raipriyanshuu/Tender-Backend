# Pipeline Debugging Guide

## Architecture Summary

**NO QUEUES USED** - This system uses direct HTTP calls, not Redis queues:

```
1. Upload (POST /upload-tender)
   ↓
2. Create processing_jobs (status='queued')
   ↓
3. Trigger (POST /api/batches/:id/process)
   ↓
4. processBatch() async
   ├─→ extractBatch() → creates file_extractions
   └─→ Loop files → HTTP POST to Python worker
       ↓
5. Worker processes each file
   ├─→ Updates DB (status='processing' → 'SUCCESS'/'FAILED')
   └─→ Returns HTTP response
       ↓
6. Mark batch complete
   ↓
7. Aggregate results
```

## Changes Applied

### 1. Added Comprehensive Logging

**File: `src/services/orchestrator.js`**
- Logs batch start, run_id, file counts
- Logs each file processing attempt with timing
- Logs worker HTTP errors with full details
- Logs final success/failure counts

**File: `src/services/zipExtractor.js`**
- Logs ZIP extraction details
- Lists all files found (supported and unsupported)
- Logs file_extractions creation
- Logs final totals and run_id

**File: `src/services/workerClient.js`**
- Logs HTTP errors with status codes
- Detects ECONNREFUSED (worker not running)
- Logs worker response data on errors

### 2. Better Error Handling

- Worker client now logs detailed HTTP error information
- Distinguishes between network errors (worker down) vs. processing errors (worker returned 500)

## How to Debug

### Step 1: Restart Backend to Load New Logs

```powershell
# Stop backend (Ctrl+C)
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
npm start
```

**Expected startup message:**
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

**If worker not running:**
```powershell
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
uvicorn workers.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3: Upload Test ZIP

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://localhost:3001/upload-tender `
  -Form @{file=Get-Item "path\to\test.zip"}
```

**Response:**
```json
{
  "success": true,
  "batch_id": "batch_abc..."
}
```

**Backend logs should show:**
```
(no logs yet - upload is simple file write)
```

### Step 4: Trigger Processing

```powershell
$batchId = "batch_abc..."  # From Step 3

Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:3001/api/batches/$batchId/process" `
  -ContentType "application/json" `
  -Body '{"concurrency":2}'
```

**Response (immediate):**
```json
{
  "success": true,
  "message": "Processing started for batch batch_abc...",
  "batch_id": "batch_abc..."
}
```

### Step 5: Watch Backend Logs

**Backend terminal should show:**

```
[Orchestrator] Starting batch batch_abc... with concurrency=2
[Orchestrator] Batch status: queued, run_id: null
[Orchestrator] Extracting ZIP for batch batch_abc...
[ZipExtractor] Starting extraction for batch batch_abc...
[ZipExtractor] Batch found, zip_path: uploads\batch_abc....zip
[ZipExtractor] ZIP path: C:\Users\DELL\...\shared\uploads\batch_abc....zip
[ZipExtractor] Extract to: C:\Users\DELL\...\shared\extracted\batch_abc...
[ZipExtractor] ZIP extracted successfully
[ZipExtractor] Found 24 total items in extract directory
[ZipExtractor]   ✓ file1.pdf (.pdf)
[ZipExtractor]   ✓ file2.docx (.docx)
...
[ZipExtractor] 24 supported files found
[ZipExtractor] Creating file_extractions records with run_id: batch_abc...
[ZipExtractor]   Created: batch_abc..._uuid1 → file1.pdf
...
[ZipExtractor] Batch updated: total_files=24, run_id=batch_abc..., status=queued
[Orchestrator] Extraction complete: 24 files extracted
[Orchestrator] Using run_id: batch_abc...
[Orchestrator] Found 24 files to process (pending or retryable)
[Orchestrator] Processing 24 files with 2 workers...
[Orchestrator] → Processing file: batch_abc..._uuid1 (file1.pdf)
[Orchestrator] → Processing file: batch_abc..._uuid2 (file2.docx)
[Orchestrator] ✓ File batch_abc..._uuid1 completed in 15234ms
[Orchestrator] → Processing file: batch_abc..._uuid3 (file3.pdf)
...
[Orchestrator] Processing complete: 24 succeeded, 0 failed
[Orchestrator] Batch batch_abc... marked as completed
[Orchestrator] Starting aggregation for batch batch_abc...
[Orchestrator] Aggregation complete for batch batch_abc...
```

### Step 6: Watch Worker Logs

**Worker terminal should show (for each file):**

```
Processing file: C:\Users\DELL\...\shared\extracted\batch_abc...\file1.pdf
Parsed 12345 characters from C:\Users\...\file1.pdf
Split into 4 chunks, calling LLM...
Successfully processed batch_abc..._uuid1
INFO:     127.0.0.1:xxxxx - "POST /process-file HTTP/1.1" 200 OK
```

### Step 7: Monitor Status

```powershell
# Check every 10 seconds
Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/status"
```

**Expected progression:**
```
Initial:
  batch_status: processing
  files_pending: 24
  files_processing: 0
  files_success: 0
  files_failed: 0

During (after 20-30 seconds):
  batch_status: processing
  files_pending: 18
  files_processing: 2
  files_success: 4
  files_failed: 0

Final (after 5-15 minutes):
  batch_status: completed
  files_pending: 0
  files_processing: 0
  files_success: 24
  files_failed: 0
  progress_percent: 100.00
```

## Diagnostic Patterns

### Pattern 1: Worker Not Running

**Backend logs:**
```
[Orchestrator] → Processing file: batch_abc..._uuid1 (file1.pdf)
[WorkerClient] processFile failed for batch_abc..._uuid1:
  Message: connect ECONNREFUSED 127.0.0.1:8000
  Code: ECONNREFUSED (Worker not reachable)
[Orchestrator] ✗ File batch_abc..._uuid1 failed: connect ECONNREFUSED
```

**Fix:**
```powershell
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
uvicorn workers.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Pattern 2: Worker Returning 500 (Processing Errors)

**Backend logs:**
```
[Orchestrator] → Processing file: batch_abc..._uuid1 (file1.pdf)
[WorkerClient] processFile failed for batch_abc..._uuid1:
  Message: Request failed with status code 500
  Status: 500
  Data: {"detail":"File not found at path: ..."}
[Orchestrator] ✗ File batch_abc..._uuid1 failed: Request failed with status code 500
```

**Worker logs:**
```
INFRASTRUCTURE ERROR processing batch_abc..._uuid1: ValueError: File not found at path: ...
INFO:     127.0.0.1:xxxxx - "POST /process-file HTTP/1.1" 500 Internal Server Error
```

**Check:**
- Are files actually extracted? Look at `C:\Users\DELL\OneDrive\Desktop\tenderBackend\shared\extracted\batch_abc...`
- Does worker have permission to read files?
- Are file_path values correct in DB?

### Pattern 3: Worker Processing But All Fail

**Backend logs:**
```
[Orchestrator] → Processing file: batch_abc..._uuid1 (file1.pdf)
[Orchestrator] ✓ File batch_abc..._uuid1 completed in 234ms  # Fast completion (suspicious)
...
[Orchestrator] Processing complete: 0 succeeded, 24 failed
```

**Worker logs:**
```
Processing file: C:\Users\DELL\...\file1.pdf
Failed to process batch_abc..._uuid1: OpenAI client initialization failed
INFO:     127.0.0.1:xxxxx - "POST /process-file HTTP/1.1" 200 OK  # Returns 200 but marked as failed in DB
```

**Check:**
- Query DB for actual errors:
  ```powershell
  Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/errors"
  ```
- Common causes:
  - OpenAI API key invalid/expired
  - Parsing errors (corrupt PDFs)
  - File not found (path issue)

### Pattern 4: No Files Found After Extraction

**Backend logs:**
```
[ZipExtractor] 24 supported files found
[ZipExtractor] Creating file_extractions records with run_id: batch_abc...
[Orchestrator] Extraction complete: 24 files extracted
[Orchestrator] Using run_id: batch_abc...
[Orchestrator] Found 0 files to process (pending or retryable)
[Orchestrator] No files to process for batch batch_abc...
```

**Cause:** Run ID mismatch between processing_jobs and file_extractions

**Fix:** Check DB:
```sql
-- Should return batch details with run_id set
SELECT batch_id, run_id, total_files FROM processing_jobs WHERE batch_id = 'batch_abc...';

-- Should return 24 files with matching run_id
SELECT COUNT(*), run_id, status FROM file_extractions WHERE run_id = 'batch_abc...' GROUP BY run_id, status;
```

### Pattern 5: Extraction Fails

**Backend logs:**
```
[ZipExtractor] Starting extraction for batch batch_abc...
[ZipExtractor] ZIP path: C:\Users\DELL\...\uploads\batch_abc....zip
[Orchestrator] Extraction failed for batch_abc...: Error: ENOENT: no such file or directory
```

**Cause:** ZIP file not found

**Fix:**
- Check uploads folder exists: `C:\Users\DELL\OneDrive\Desktop\tenderBackend\shared\uploads\`
- Verify ZIP was actually uploaded
- Check file permissions

## Quick Diagnostic Commands

```powershell
# 1. Check if worker is reachable
Invoke-RestMethod http://localhost:8000/health

# 2. Get batch status
Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/status"

# 3. Get failed file errors
Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/errors"

# 4. Get all files for batch
Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/files"

# 5. Check backend health
Invoke-RestMethod http://localhost:3001/health

# 6. Verify extracted files exist (PowerShell)
Get-ChildItem "C:\Users\DELL\OneDrive\Desktop\tenderBackend\shared\extracted\$batchId" -Recurse -File | Select-Object Name

# 7. Count file_extractions in DB (via psql)
psql -h 127.0.0.1 -U postgres -d tender_db -c "SELECT COUNT(*), status FROM file_extractions WHERE run_id = '$batchId' GROUP BY status;"
```

## Expected Timing

- **Extraction**: 1-3 seconds for 24 files
- **Processing per file**: 10-60 seconds (depends on file size, LLM response)
- **Total for 24 files with concurrency=2**: 5-30 minutes
- **Aggregation**: 1-2 seconds

**Red flags:**
- Batch completes in < 10 seconds → Files not actually processed
- All files FAILED → Check errors endpoint
- Worker logs show no activity → Worker not receiving requests (check URL)

## Next Steps

After applying these logging changes:

1. **Restart backend** to load new code
2. **Upload a test ZIP** with 2-3 small PDFs
3. **Trigger processing** with concurrency=2
4. **Watch BOTH terminals** (backend and worker)
5. **Report findings**:
   - At what point do logs stop making sense?
   - What errors appear in backend logs?
   - What errors appear in worker logs?
   - What does status endpoint show?
   - What does errors endpoint show?

The logs will pinpoint the exact failure point.
