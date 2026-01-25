# 🚨 QUICK FIX: Missing Database Tables

## Your Problem
- Your PostgreSQL DB only has: `file_extractions`, `run_summaries`
- Worker shows: `password authentication failed` or `relation "processing_jobs" does not exist`
- Backend expects: `processing_jobs`, `system_alerts`, and 6 views

## Fix in 3 Steps (5 minutes)

### Step 1: Fix DB Password in Worker Config
```powershell
# Test your Postgres login:
psql -U postgres -h 127.0.0.1 -p 5432 -d tender_db
```

If password prompt appears, enter your real Windows Postgres password.

**Then update both:**
- `tenderBackend/.env`
- `tenderBackend/workers/.env`

Change this line:
```env
DATABASE_URL=postgresql://postgres:YOUR_REAL_PASSWORD@127.0.0.1:5432/tender_db
```

### Step 2: Run the Database Migration
```powershell
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
node run-migration.js 001_002_003_005_consolidated_idempotent.sql
```

**Expected output:**
```
✅ Migration completed successfully!
✅ All expected tables and views are present!

📊 TABLES:
  ✓ file_extractions
  ✓ processing_jobs
  ✓ run_summaries
  ✓ system_alerts

👁️  VIEWS:
  ✓ active_batches_monitor
  ✓ batch_history_summary
  ✓ batch_status_summary
  ✓ error_summary_by_type
  ✓ failed_files_report
  ✓ processing_performance_metrics
```

### Step 3: Restart Worker and Test
```powershell
# Terminal 1: Start worker
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
uvicorn workers.api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Test health
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "storage_path": "C:\\Users\\DELL\\OneDrive\\Desktop\\tenderBackend\\shared",
    "disk_usage_percent": 42.5,
    "parsers_ready": true,
    "llm_configured": true
  }
}
```

## If Still Broken

### Worker Error: "password authentication failed"
**Fix:** Your DATABASE_URL password is wrong.
1. Check what password you set during Postgres install (on Windows)
2. Update both `.env` files (backend + workers)
3. Restart worker

### Worker Error: "could not connect to server"
**Fix:** PostgreSQL service not running.
```powershell
# Start Postgres service (as admin)
net start postgresql-x64-15
```

### Backend Error: "relation processing_jobs does not exist"
**Fix:** Migration didn't run.
```powershell
# Verify migration ran:
node run-migration.js verify
```

### Worker Error: "No module named 'fastapi'"
**Fix:** Worker dependencies not installed.
```powershell
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend\workers
pip install -r requirements.txt
```

## Next Steps After Fix

1. **Start backend:**
   ```powershell
   cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
   npm start
   ```

2. **Test backend health:**
   ```powershell
   curl http://localhost:3001/health
   ```

3. **Continue with testing guide:**
   Open `QUICK_START_TESTING.md`

## Files Created to Help You

- ✅ `SCHEMA_FIX_INSTRUCTIONS.md` - Detailed explanation
- ✅ `001_002_003_005_consolidated_idempotent.sql` - The migration
- ✅ `run-migration.js` - Migration runner script
- ✅ `QUICK_FIX.md` - This file
- ✅ `migrations/README_MIGRATIONS.md` - Updated with quick start

## Still Stuck?

Check your terminal output for the **exact error message** and search for it in:
- `SCHEMA_FIX_INSTRUCTIONS.md` (Troubleshooting section)
- `LOCALHOST_TESTING_GUIDE.md` (Dependencies section)
