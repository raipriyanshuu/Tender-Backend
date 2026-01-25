# Fix: OpenAI Client Initialization Error

## Issue Diagnosed

**Error**: `Client.__init__() got an unexpected keyword argument 'proxies'`

**Cause**: The `openai` package version 1.10.0 has a compatibility issue with proxy environment variables or certain system configurations. When the OpenAI client tries to initialize, it fails with a TypeError about an unexpected 'proxies' argument.

## Status Before Fix

- ✅ Files moved from `pending` to `FAILED` (transaction fix working)
- ❌ All 24 files failed with OpenAI client initialization error
- ✅ File extraction working correctly
- ✅ File paths correct (files exist on disk)

## Root Cause

The `openai==1.10.0` package has issues with:
1. Proxy environment variable detection
2. Parameter compatibility with certain system configurations
3. Outdated initialization parameters

All 24 files failed in ~5 seconds because the error occurred immediately when trying to create the OpenAI client, before any actual LLM API calls were made.

## Fix Applied

### File: `workers/requirements.txt`
**Changed**: Updated openai package version
```diff
- openai==1.10.0
+ openai>=1.30.0
```

### File: `workers/processing/llm_client.py`
**Added**: Better error handling for OpenAI client initialization
```python
try:
    client = OpenAI(api_key=config.openai_api_key)
except TypeError as exc:
    if 'proxies' in str(exc):
        raise LLMError(
            "OpenAI client initialization failed. Please upgrade the openai package: "
            "pip install --upgrade openai"
        ) from exc
    raise
```

### File: `workers/processing/extractor.py`
**Added**: File existence check for better error messages
```python
# Check if file exists
import os
if not os.path.exists(full_path):
    raise ValueError(f"File not found at path: {full_path}")
```

## How to Apply the Fix

### Step 1: Upgrade OpenAI Package
```powershell
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend\workers
pip install --upgrade openai
```

**Expected output:**
```
Successfully installed openai-1.XX.X
```

### Step 2: Verify Installation
```powershell
pip show openai
```

**Expected output:**
```
Name: openai
Version: 1.30.0 (or higher)
```

### Step 3: Restart Worker
```powershell
# Stop current worker (Ctrl+C in the worker terminal)

# Start worker fresh
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
uvicorn workers.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 4: Test with the Failed Batch

You can retry the failed batch:
```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://localhost:3001/api/batches/batch_c820f2d3-8dc0-4ad2-9999-29ba2cb8aa9c/retry-failed `
  -ContentType "application/json" `
  -Body '{}'
```

Or upload a new small test batch:
```powershell
# Upload a test ZIP with 1-2 PDFs
Invoke-RestMethod `
  -Method POST `
  -Uri http://localhost:3001/upload-tender `
  -Form @{file=Get-Item "test.zip"}
```

### Step 5: Monitor Status
```powershell
# Check status (replace BATCH_ID)
Invoke-RestMethod http://localhost:3001/api/batches/BATCH_ID/status
```

**Expected output after fix:**
```powershell
batch_status    : completed
total_files     : 24
files_success   : 24  # Should be > 0 now
files_failed    : 0   # Should be 0 or much lower
files_pending   : 0
files_processing: 0
progress_percent: 100.00
```

## What Changed

| Before Fix | After Fix |
|------------|-----------|
| Files fail with OpenAI client error | OpenAI client initializes successfully |
| All files FAILED in 5 seconds | Files process normally (20-60 seconds each) |
| Error: "unexpected keyword argument 'proxies'" | LLM extracts data successfully |

## Verification

After applying the fix, you should see:

1. **Worker starts without errors**
2. **Files process successfully** with LLM extraction
3. **Processing takes longer** (normal - each file needs LLM calls)
4. **Some files may succeed** (depending on PDF quality and API key validity)

### Check Worker Logs

Watch the worker terminal for these log messages:
```
Processing file: C:\Users\DELL\OneDrive\Desktop\tenderBackend\shared\extracted\...
Parsed 12345 characters from ...
Split into 4 chunks, calling LLM...
Successfully processed doc_id
```

### If Files Still Fail

If files still fail after the upgrade, check:

1. **OpenAI API Key**: Verify it's valid and has credits
   ```powershell
   # Check the key is set in workers/.env
   cat workers\.env | Select-String OPENAI_API_KEY
   ```

2. **OpenAI API Status**: Visit https://status.openai.com/

3. **API Key Quota**: Check your OpenAI dashboard for rate limits

4. **Check specific errors**:
   ```powershell
   Invoke-RestMethod http://localhost:3001/api/batches/BATCH_ID/errors
   ```

## Summary

- **Root Cause**: Outdated `openai` package (1.10.0) with proxy handling bug
- **Solution**: Upgrade to `openai>=1.30.0`
- **Impact**: All files can now process successfully
- **Action Required**: Run `pip install --upgrade openai` and restart worker

## Expected Behavior After Fix

✅ Files move through: `pending` → `processing` → `SUCCESS`  
✅ LLM extracts data from PDFs  
✅ Processing takes appropriate time (~30s per file with 3 retries)  
✅ Batch completes with successful extractions  
✅ Summary is generated correctly  
