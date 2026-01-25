# Database Schema Fix Instructions

## Problem Summary

Your database only has the **original 2 tables** from the initial N8N setup:
- ✅ `file_extractions`
- ✅ `run_summaries`

**Missing tables and views** that the application code expects:
- ❌ `processing_jobs` table (batch tracking)
- ❌ `system_alerts` table (monitoring)
- ❌ 6 monitoring views
- ❌ Extended columns in `file_extractions` (file_path, retry_count, error_type, etc.)

## Root Cause

You only ran `create_n8n_tables.sql` but never ran migrations:
- `001_processing_jobs_table.sql`
- `002_extend_file_extractions.sql`
- `003_database_views.sql`
- `005_monitoring_tables.sql`

## Solution

### Step 1: Run the Consolidated Migration

A single idempotent migration file has been created that safely applies all missing changes:

```powershell
# From tenderBackend directory
node run-migration.js 001_002_003_005_consolidated_idempotent.sql
```

**Expected output:**
```
📄 Reading migration: ...
🚀 Executing migration...
✅ Migration completed successfully!

🔍 Verifying database schema...

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

✅ All expected tables and views are present!
```

### Step 2: Verify Schema Manually (Optional)

Connect to your database and verify:

```sql
-- Check tables
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Check views
SELECT viewname FROM pg_views WHERE schemaname = 'public';

-- Test a view
SELECT * FROM batch_status_summary LIMIT 1;
```

### Step 3: Verify Worker Health

After the migration, restart the worker and test:

```powershell
# Stop current worker (Ctrl+C if running)

# Start worker
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
uvicorn workers.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Test health endpoint:
```powershell
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "storage_path": "...",
    "disk_usage_percent": 45.2,
    "parsers_ready": true,
    "llm_configured": true
  }
}
```

### Step 4: Verify Backend Endpoints

Start the backend:
```powershell
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
npm start
```

Test backend health:
```powershell
curl http://localhost:3001/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-23T...",
  "checks": {
    "database": { "status": "ok", "latency_ms": 15 },
    "worker_api": { "status": "ok", "latency_ms": 8 },
    "filesystem": { "status": "ok" },
    "recent_batches": { "status": "ok", "success_rate_percent": 100 }
  }
}
```

## Safety Features

The consolidated migration is **idempotent** - safe to run multiple times:
- Uses `CREATE TABLE IF NOT EXISTS`
- Uses `ALTER TABLE ADD COLUMN IF NOT EXISTS`
- Uses `CREATE OR REPLACE VIEW`
- Uses `DROP TRIGGER IF EXISTS` before creating triggers
- Checks `pg_policies` before creating RLS policies (no duplicate errors)

## Troubleshooting

### Error: "relation already exists"
**Cause:** Some tables were partially created.  
**Fix:** The migration handles this - it will skip existing objects.

### Error: "column already exists"
**Cause:** `file_extractions` was partially extended.  
**Fix:** The migration uses `ADD COLUMN IF NOT EXISTS` - safe to rerun.

### Error: "policy already exists"
**Cause:** RLS policies were created manually.  
**Fix:** The migration checks `pg_policies` before creating - safe to rerun.

### Worker still shows DB connection error
**Cause:** Incorrect DATABASE_URL in `workers/.env`  
**Fix:** 
1. Verify your Postgres password:
   ```powershell
   psql -U postgres -h 127.0.0.1 -p 5432 -d tender_db
   ```
2. Update `tenderBackend/workers/.env`:
   ```env
   DATABASE_URL=postgresql://postgres:YOUR_REAL_PASSWORD@127.0.0.1:5432/tender_db
   ```
3. Restart worker

## Next Steps After Fix

Once all services are healthy:

1. **Upload a test batch:**
   ```powershell
   curl -X POST http://localhost:3001/upload-tender -F "file=@test_tender.zip"
   ```

2. **Trigger processing:**
   ```powershell
   curl -X POST http://localhost:3001/api/batches/{batch_id}/process
   ```

3. **Monitor progress:**
   ```powershell
   curl http://localhost:3001/api/batches/{batch_id}/status
   ```

4. **Check monitoring views:**
   ```sql
   -- View batch status
   SELECT * FROM batch_status_summary;
   
   -- View failed files
   SELECT * FROM failed_files_report;
   
   -- View performance metrics
   SELECT * FROM processing_performance_metrics;
   ```

## Files Created

- `migrations/001_002_003_005_consolidated_idempotent.sql` - Single migration to fix schema
- `run-migration.js` - Node.js script to run migrations safely
- `SCHEMA_FIX_INSTRUCTIONS.md` - This file

## Documentation Updates

After applying the fix, the following docs are now accurate:
- ✅ `LOCALHOST_TESTING_GUIDE.md` - Database setup section
- ✅ `QUICK_START_TESTING.md` - Prerequisites section
- ✅ Worker health checks
- ✅ Backend monitoring endpoints
