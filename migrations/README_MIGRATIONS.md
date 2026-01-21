# Database Migrations

This directory contains SQL migration files for the tender processing system.

## Migration Files

### 001_processing_jobs_table.sql
**Purpose**: Create the `processing_jobs` table for batch-level tracking

**Creates**:
- `processing_jobs` table with columns: id, batch_id, zip_path, run_id, total_files, status, etc.
- Indexes for performance (batch_id, status, created_at)
- Auto-update trigger for updated_at timestamp
- Row Level Security policies

**Status Values**:
- `pending` - Batch created, not yet started
- `queued` - Batch queued for processing
- `extracting` - ZIP being extracted
- `processing` - Files being processed
- `completed` - All files processed successfully
- `completed_with_errors` - Some files failed but batch completed
- `failed` - Batch failed completely

### 002_extend_file_extractions.sql
**Purpose**: Extend existing `file_extractions` table with processing metadata

**Adds**:
- `file_path` - Local filesystem path
- `processing_started_at` - Start timestamp
- `processing_completed_at` - End timestamp
- `processing_duration_ms` - Auto-calculated duration
- `retry_count` - Number of retry attempts
- `error_type` - Error classification

**Indexes**:
- `(run_id, status)` - For batch status queries
- `(status, error_type)` - For failed files queries
- `(retry_count)` - For monitoring retries

**Triggers**:
- Auto-calculate `processing_duration_ms` on insert/update

### 003_database_views.sql
**Purpose**: Create convenience views for common queries

**Views Created**:
1. **batch_status_summary** - Real-time batch progress
   - File counts (success/failed/processing/pending)
   - Progress percentage
   - Timing statistics

2. **failed_files_report** - List of failed files with errors
   - Error details and types
   - Retry counts
   - Processing times

3. **processing_performance_metrics** - Daily performance stats
   - Average processing times
   - Error rate by type
   - Retry statistics

4. **active_batches_monitor** - Currently processing batches
   - Real-time progress
   - Currently processing files
   - Elapsed time

5. **batch_history_summary** - Historical batch records
   - Completed batches
   - Success rates
   - Total duration

### 004_seed_test_data.sql
**Purpose**: Insert test data for development and testing

**Test Scenarios**:
1. **test_batch_001** - Completed batch (3 files, all successful)
2. **test_batch_002** - Processing batch (5 files, 2 done, 1 processing, 2 pending)
3. **test_batch_003** - Completed with errors (4 files, 2 success, 2 failed)
4. **test_batch_004** - Fresh batch (just queued)

**⚠️ WARNING**: Only run in development! Clears existing test data.

## How to Run Migrations

### Option 1: Supabase Dashboard
1. Go to https://supabase.com/dashboard
2. Select your project
3. Navigate to **SQL Editor**
4. Click **New query**
5. Copy and paste migration file contents
6. Click **Run**

### Option 2: Command Line (psql)
```bash
# Set your database URL
export DATABASE_URL="postgresql://user:password@host:port/database"

# Run migrations in order
psql $DATABASE_URL -f migrations/001_processing_jobs_table.sql
psql $DATABASE_URL -f migrations/002_extend_file_extractions.sql
psql $DATABASE_URL -f migrations/003_database_views.sql

# Optional: Seed test data (development only)
psql $DATABASE_URL -f migrations/004_seed_test_data.sql
```

### Option 3: Node.js Script
```bash
# Use the provided migration runner
node run-migration.js 001_processing_jobs_table.sql
node run-migration.js 002_extend_file_extractions.sql
node run-migration.js 003_database_views.sql

# Optional: Test data
node run-migration.js 004_seed_test_data.sql
```

## Verification

After running migrations, verify with these queries:

```sql
-- Check tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('processing_jobs', 'file_extractions', 'run_summaries');

-- Check columns added to file_extractions
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'file_extractions' 
  AND column_name IN ('file_path', 'retry_count', 'error_type');

-- Check views created
SELECT table_name 
FROM information_schema.views 
WHERE table_schema = 'public';

-- Test views with data
SELECT * FROM batch_status_summary LIMIT 5;
SELECT * FROM failed_files_report LIMIT 5;
SELECT * FROM active_batches_monitor LIMIT 5;
```

## Testing Queries

```sql
-- Test batch creation
INSERT INTO processing_jobs (batch_id, zip_path, total_files, status)
VALUES ('test_manual', '/shared/uploads/test.zip', 5, 'queued');

-- Test file extraction creation
INSERT INTO file_extractions (doc_id, run_id, filename, status)
VALUES ('test_file', 'test_manual', 'test.pdf', 'pending');

-- Check batch status
SELECT * FROM batch_status_summary WHERE batch_id = 'test_manual';

-- Cleanup
DELETE FROM file_extractions WHERE run_id = 'test_manual';
DELETE FROM processing_jobs WHERE batch_id = 'test_manual';
```

## Migration Order

**IMPORTANT**: Run migrations in this order:
1. 001_processing_jobs_table.sql (creates new table)
2. 002_extend_file_extractions.sql (extends existing table)
3. 003_database_views.sql (creates views referencing both tables)
4. 004_seed_test_data.sql (optional - test data only)

## Rollback

To rollback migrations:

```sql
-- Drop views
DROP VIEW IF EXISTS batch_history_summary CASCADE;
DROP VIEW IF EXISTS active_batches_monitor CASCADE;
DROP VIEW IF EXISTS processing_performance_metrics CASCADE;
DROP VIEW IF EXISTS failed_files_report CASCADE;
DROP VIEW IF EXISTS batch_status_summary CASCADE;

-- Remove added columns from file_extractions
ALTER TABLE file_extractions 
  DROP COLUMN IF EXISTS error_type,
  DROP COLUMN IF EXISTS retry_count,
  DROP COLUMN IF EXISTS processing_duration_ms,
  DROP COLUMN IF EXISTS processing_completed_at,
  DROP COLUMN IF EXISTS processing_started_at,
  DROP COLUMN IF EXISTS file_path;

-- Drop processing_jobs table
DROP TABLE IF EXISTS processing_jobs CASCADE;
```

## Next Steps

After running Phase 1 migrations:
- ✅ Database schema is ready
- ✅ Test data available (if seeded)
- ✅ Views provide useful queries
- ➡️ Ready for Phase 2: Shared Filesystem Setup
- ➡️ Ready for Phase 3: Python Workers - Core Services

## Support

If you encounter issues:
1. Check PostgreSQL version (15+ required)
2. Verify JSONB support enabled
3. Check user permissions (CREATE TABLE, CREATE INDEX, etc.)
4. Review migration file comments for requirements
5. Test with seed data first before production use
