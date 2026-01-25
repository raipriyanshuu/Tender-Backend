# Critical Fix: Files Stuck in Pending Status

## Problem Analysis

Your batch processing showed:
- ✅ 24 files uploaded and extracted
- ❌ 0 files processed successfully
- ❌ 0 files failed
- ❌ 24 files stuck in "pending" status

**Root Cause**: The worker was returning HTTP 500 errors for every file, causing database transactions to rollback and leaving files in "pending" status instead of marking them as "FAILED".

## What Was Broken

### 1. **Transaction Rollback Issue**
The worker's exception handling was causing status updates to be rolled back:
```
1. Worker marks file as "processing"
2. LLM call fails (invalid API key, quota, etc.)
3. Exception raised → transaction rolled back
4. File reverts to "pending" instead of "FAILED"
5. Endpoint returns 500
```

### 2. **Missing Error Handling**
Processing errors (LLM failures, parsing errors) were being treated as infrastructure errors, causing the endpoint to return 500 instead of gracefully handling the failure.

### 3. **No API Key Validation**
The worker wasn't checking if the OpenAI API key was valid before attempting to process files.

## Fixes Applied

### File: `workers/processing/extractor.py`
**Changed**: Removed `raise` at the end of exception handler
**Effect**: Processing errors are now caught, logged, and marked as FAILED without rolling back the transaction

```python
except Exception as exc:
    logger.error(f"Failed to process {doc_id}: {exc}")
    error_type = classify_error(exc)
    operations.mark_file_failed(session, doc_id, str(exc), error_type)
    # Don't re-raise - let the endpoint return success after committing the failure
```

### File: `workers/processing/llm_client.py`
**Added**: API key validation before making LLM calls
**Effect**: Clear error message if API key is missing or invalid

```python
if not config.openai_api_key or config.openai_api_key == "your_openai_api_key_here":
    raise LLMError("OPENAI_API_KEY is not configured. Please set a valid API key in workers/.env")
```

### File: `workers/api/main.py`
**Changed**: Updated health check to validate LLM configuration
**Effect**: Health endpoint now shows if API key is missing

```python
llm_configured = bool(config.openai_api_key) and config.openai_api_key != "your_openai_api_key_here"
llm_status = "ok" if llm_configured else "missing_or_invalid_api_key"
```

### File: `workers/database/operations.py`
**Fixed**: Replaced `.cast(int)` with `case()` for PostgreSQL compatibility
**Effect**: Aggregation endpoint no longer returns 500 errors

## How to Test the Fix

### Step 1: Restart the Worker
```powershell
# Stop current worker (Ctrl+C)
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
uvicorn workers.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 2: Check Worker Health
```powershell
Invoke-RestMethod http://localhost:8000/health
```

**Expected Output**:
```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "storage_path": "...",
    "disk_usage_percent": 42.5,
    "parsers_ready": true,
    "llm_configured": true,
    "llm_status": "ok"
  }
}
```

**If `llm_status` is `"missing_or_invalid_api_key"`**, check your `workers/.env` file:
```bash
OPENAI_API_KEY=sk-proj-...  # Must be a valid OpenAI API key
```

### Step 3: Upload a New Test Batch
```powershell
# Upload a small ZIP with 1-2 PDFs for testing
Invoke-RestMethod http://localhost:3001/upload-tender `
  -Method Post `
  -Form @{file=Get-Item "test.zip"}
```

### Step 4: Trigger Processing
```powershell
# Replace BATCH_ID with the actual batch_id from Step 3
Invoke-RestMethod http://localhost:3001/api/batches/BATCH_ID/process `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"concurrency": 2}'
```

### Step 5: Monitor Status
```powershell
# Check status every few seconds
Invoke-RestMethod http://localhost:3001/api/batches/BATCH_ID/status
```

**Expected Output** (after processing completes):
```powershell
batch_status    : completed  # or completed_with_errors if some files failed
total_files     : 2
files_success   : 2  # or 0 if API key is invalid
files_failed    : 0  # or 2 if API key is invalid
files_pending   : 0  # Should be 0, not stuck
files_processing: 0
```

### Step 6: Check for Errors
```powershell
# If files_failed > 0, check the errors
Invoke-RestMethod http://localhost:3001/api/batches/BATCH_ID/errors
```

## Expected Behavior After Fix

### ✅ If OpenAI API Key is Valid:
- Files move from `pending` → `processing` → `SUCCESS`
- `files_success` increases
- Summary is generated
- Batch completes successfully

### ✅ If OpenAI API Key is Invalid:
- Files move from `pending` → `processing` → `FAILED`
- `files_failed` increases with error message: "OPENAI_API_KEY is not configured"
- Worker returns 200 (not 500)
- Batch completes with errors
- **Files are NOT stuck in pending**

## Troubleshooting

### Issue: Health check shows `llm_status: "missing_or_invalid_api_key"`
**Fix**: Update `workers/.env` with a valid OpenAI API key
```bash
OPENAI_API_KEY=sk-proj-YOUR_ACTUAL_KEY_HERE
```

### Issue: Files still showing 500 errors in worker logs
**Fix**: Check worker terminal for the actual error message. Common causes:
- File not found: Check that ZIP extraction is working
- Parse error: Check if PDFs are corrupt
- Database error: Check DATABASE_URL in workers/.env

### Issue: Files stuck in "processing" status
**Fix**: This means the worker crashed mid-processing. Restart the worker and retry:
```powershell
Invoke-RestMethod http://localhost:3001/api/batches/BATCH_ID/retry-failed -Method Post
```

## Summary of Changes

| File | Change | Purpose |
|------|--------|---------|
| `workers/processing/extractor.py` | Don't re-raise exceptions after marking as FAILED | Prevent transaction rollback |
| `workers/processing/llm_client.py` | Validate API key before LLM calls | Clear error messages |
| `workers/api/main.py` | Enhanced health check | Detect invalid API key |
| `workers/database/operations.py` | Use `case()` instead of `cast(int)` | PostgreSQL compatibility |

## Next Steps

1. **Verify OpenAI API Key**: Make sure you have a valid, active OpenAI API key with credits
2. **Restart Worker**: Apply the fixes by restarting the worker process
3. **Test with Small Batch**: Upload 1-2 files first to verify everything works
4. **Monitor Logs**: Watch worker terminal for any error messages during processing
5. **Check Failed Files**: If any files fail, use the `/errors` endpoint to see why

## Files That Should NEVER Be Stuck in Pending Now

After this fix:
- ✅ Files will properly transition through: `pending` → `processing` → (`SUCCESS` or `FAILED`)
- ✅ Processing errors are captured and logged
- ✅ Batch completes with accurate success/failed counts
- ✅ Worker endpoints return 200 even for processing failures
- ✅ Only infrastructure errors (DB connection, session errors) return 500
