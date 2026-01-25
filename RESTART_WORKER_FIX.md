# Fix: Worker Still Using Old OpenAI Package

## Issue Found

**Error**: "OpenAI client initialization failed. Please upgrade the openai package: pip install --upgrade openai"

**Why files are still failing**: The worker process is still running with the OLD `openai==1.10.0` package loaded in memory, even though you upgraded it.

## Root Cause

When you run `pip install --upgrade openai`, it updates the package files on disk, but:
- ✅ Package upgraded on disk
- ❌ Worker process still running with old package in memory
- ❌ Worker needs to be restarted to load the new package

Python processes load packages into memory when they start. Upgrading a package doesn't affect already-running processes.

## Solution

**You MUST restart the worker for the upgrade to take effect.**

### Step 1: Stop the Worker
In the terminal where `uvicorn` is running, press:
```
Ctrl+C
```

You should see:
```
Received signal 2, shutting down gracefully...
```

### Step 2: Verify the Package was Upgraded
```powershell
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend\workers
pip show openai
```

**Expected output:**
```
Name: openai
Version: 1.30.0 (or higher, NOT 1.10.0)
```

**If it still shows 1.10.0**, run:
```powershell
pip install --upgrade openai
```

### Step 3: Start the Worker Fresh
```powershell
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
uvicorn workers.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Wait for this message:**
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 4: Verify Worker Health
```powershell
Invoke-RestMethod http://localhost:8000/health
```

**Expected output:**
```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "storage_path": "C:\\Users\\DELL\\OneDrive\\Desktop\\tenderBackend\\shared",
    "disk_usage_percent": 42.5,
    "parsers_ready": true,
    "llm_configured": true,
    "llm_status": "ok"
  }
}
```

**Important**: `llm_status` should be `"ok"`, NOT `"missing_or_invalid_api_key"`

### Step 5: Retry the Batch
```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://localhost:3001/api/batches/batch_c820f2d3-8dc0-4ad2-9999-29ba2cb8aa9c/retry-failed `
  -ContentType "application/json"
```

**Expected response:**
```json
{
  "success": true,
  "message": "Retrying 24 failed files"
}
```

### Step 6: Monitor Processing
```powershell
# Check status every 30 seconds
Invoke-RestMethod http://localhost:3001/api/batches/batch_c820f2d3-8dc0-4ad2-9999-29ba2cb8aa9c/status
```

**Watch for these changes:**
```
files_processing: 2     # Should increase from 0
files_failed: 22        # Should decrease from 24
files_success: 2        # Should increase from 0
```

### Step 7: Watch Worker Logs

In the worker terminal, you should now see:
```
Processing file: C:\Users\DELL\OneDrive\Desktop\tenderBackend\shared\extracted\...
Parsed 12345 characters from ...
Split into 4 chunks, calling LLM...
Successfully processed doc_id
```

**If you see errors**, they will be parsing or LLM errors (which is normal for some PDFs), NOT the "proxies" error.

## Common Mistakes

### ❌ Mistake 1: Not restarting the worker
- **Symptom**: Same error appears even after upgrading package
- **Fix**: Stop worker with Ctrl+C and start again

### ❌ Mistake 2: Worker running in different terminal
- **Symptom**: Can't find the worker terminal to stop it
- **Fix**: Look for terminals with `uvicorn` in the title, or restart your IDE

### ❌ Mistake 3: Wrong Python environment
- **Symptom**: `pip show openai` shows new version, but worker still fails
- **Fix**: Make sure you're in the same environment where you installed the package

## Verification Checklist

Before retrying the batch, verify:

- [ ] Worker has been stopped (Ctrl+C)
- [ ] `pip show openai` shows version >= 1.30.0
- [ ] Worker has been started fresh
- [ ] `http://localhost:8000/health` returns `llm_status: "ok"`
- [ ] Backend is still running on port 3001

## Expected Behavior After Restart

### ✅ If OpenAI API Key is Valid:
- Files process successfully (20-60 seconds each)
- `files_success` increases
- Worker logs show LLM calls happening
- Batch completes with extractions

### ✅ If OpenAI API Key is Invalid:
- Files fail with clear error: "OPENAI_API_KEY is not configured"
- No more "proxies" error
- Batch completes quickly with clear error messages

## Troubleshooting

### Issue: Worker won't stop
**Fix**: 
```powershell
# Find the process
Get-Process | Where-Object {$_.ProcessName -like "*python*"}

# Kill it (replace PID with actual process ID)
Stop-Process -Id PID -Force
```

### Issue: Port 8000 already in use
**Fix**:
```powershell
# Find what's using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID)
Stop-Process -Id PID -Force
```

### Issue: Package upgrade fails
**Fix**:
```powershell
# Uninstall old version first
pip uninstall openai -y

# Install new version
pip install "openai>=1.30.0"
```

## Summary

**Root Cause**: Worker not restarted after package upgrade  
**Solution**: Stop worker (Ctrl+C) → Start worker → Retry batch  
**Expected Result**: Files process with LLM calls (not instant failure)  
**Time**: Processing should take 10-30 minutes for 24 files (not 5 seconds)  

## Next Steps After Worker Restart

1. **Retry the failed batch** (Step 5 above)
2. **Watch the worker logs** for actual processing
3. **Monitor status** to see files moving to SUCCESS
4. **If files still fail**, check the new error messages - they will be different (parsing or LLM errors, not "proxies")
