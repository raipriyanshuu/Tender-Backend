/*
  CONSOLIDATED IDEMPOTENT MIGRATION
  Safely applies all missing schema changes to bring your DB up to date.
  
  Safe to run multiple times (idempotent).
  
  What this does:
  - Creates processing_jobs table
  - Extends file_extractions with new columns
  - Creates 5 monitoring views
  - Creates system_alerts table
  - Creates error_summary_by_type view
  - Adds RLS policies (only if they don't exist)
*/

-- ====================================================================
-- 001: CREATE processing_jobs TABLE
-- ====================================================================
CREATE TABLE IF NOT EXISTS processing_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id text UNIQUE NOT NULL,
  zip_path text NOT NULL,
  run_id text,
  total_files integer NOT NULL DEFAULT 0,
  uploaded_by text,
  status text NOT NULL DEFAULT 'pending',
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_processing_jobs_batch_id ON processing_jobs(batch_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_created_at ON processing_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status_created ON processing_jobs(status, created_at DESC);

-- Auto-update trigger for updated_at
CREATE OR REPLACE FUNCTION update_processing_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_processing_jobs_updated_at ON processing_jobs;
CREATE TRIGGER trigger_update_processing_jobs_updated_at
  BEFORE UPDATE ON processing_jobs
  FOR EACH ROW
  EXECUTE FUNCTION update_processing_jobs_updated_at();

-- Enable RLS
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;

-- RLS Policies (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'processing_jobs' AND policyname = 'Public can view processing jobs'
  ) THEN
    CREATE POLICY "Public can view processing jobs"
      ON processing_jobs FOR SELECT TO public USING (true);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'processing_jobs' AND policyname = 'Public can insert processing jobs'
  ) THEN
    CREATE POLICY "Public can insert processing jobs"
      ON processing_jobs FOR INSERT TO public WITH CHECK (true);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'processing_jobs' AND policyname = 'Public can update processing jobs'
  ) THEN
    CREATE POLICY "Public can update processing jobs"
      ON processing_jobs FOR UPDATE TO public USING (true);
  END IF;
END $$;

-- ====================================================================
-- 002: EXTEND file_extractions TABLE
-- ====================================================================
ALTER TABLE file_extractions 
  ADD COLUMN IF NOT EXISTS file_path text,
  ADD COLUMN IF NOT EXISTS processing_started_at timestamptz,
  ADD COLUMN IF NOT EXISTS processing_completed_at timestamptz,
  ADD COLUMN IF NOT EXISTS processing_duration_ms integer,
  ADD COLUMN IF NOT EXISTS retry_count integer DEFAULT 0,
  ADD COLUMN IF NOT EXISTS error_type text;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_file_extractions_run_status 
  ON file_extractions(run_id, status);

CREATE INDEX IF NOT EXISTS idx_file_extractions_run_id_created 
  ON file_extractions(run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_file_extractions_status_error_type 
  ON file_extractions(status, error_type) 
  WHERE status = 'FAILED';

CREATE INDEX IF NOT EXISTS idx_file_extractions_retry_count 
  ON file_extractions(retry_count) 
  WHERE retry_count > 0;

-- Constraints
ALTER TABLE file_extractions 
  DROP CONSTRAINT IF EXISTS check_file_extractions_status;

ALTER TABLE file_extractions 
  ADD CONSTRAINT check_file_extractions_status 
  CHECK (status IN ('pending', 'processing', 'SUCCESS', 'FAILED', 'SKIPPED'));

ALTER TABLE file_extractions 
  DROP CONSTRAINT IF EXISTS check_file_extractions_error_type;

ALTER TABLE file_extractions 
  ADD CONSTRAINT check_file_extractions_error_type 
  CHECK (error_type IS NULL OR error_type IN ('RETRYABLE', 'PERMANENT', 'TIMEOUT', 'RATE_LIMIT', 'PARSE_ERROR', 'LLM_ERROR', 'UNKNOWN'));

-- Processing duration trigger
CREATE OR REPLACE FUNCTION calculate_processing_duration()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.processing_completed_at IS NOT NULL AND NEW.processing_started_at IS NOT NULL THEN
    NEW.processing_duration_ms = EXTRACT(EPOCH FROM (NEW.processing_completed_at - NEW.processing_started_at)) * 1000;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_calculate_processing_duration ON file_extractions;
CREATE TRIGGER trigger_calculate_processing_duration
  BEFORE INSERT OR UPDATE ON file_extractions
  FOR EACH ROW
  EXECUTE FUNCTION calculate_processing_duration();

-- ====================================================================
-- 003: CREATE MONITORING VIEWS
-- ====================================================================

-- View 1: Batch Status Summary
CREATE OR REPLACE VIEW batch_status_summary AS
SELECT 
  pj.batch_id,
  pj.status as batch_status,
  pj.zip_path,
  pj.total_files,
  pj.created_at as batch_created_at,
  pj.updated_at as batch_updated_at,
  pj.completed_at as batch_completed_at,
  
  COUNT(fe.id) as files_tracked,
  COUNT(fe.id) FILTER (WHERE fe.status = 'SUCCESS') as files_success,
  COUNT(fe.id) FILTER (WHERE fe.status = 'FAILED') as files_failed,
  COUNT(fe.id) FILTER (WHERE fe.status = 'processing') as files_processing,
  COUNT(fe.id) FILTER (WHERE fe.status = 'pending') as files_pending,
  
  CASE 
    WHEN pj.total_files > 0 THEN 
      ROUND((COUNT(fe.id) FILTER (WHERE fe.status IN ('SUCCESS', 'FAILED'))::numeric / pj.total_files::numeric) * 100, 2)
    ELSE 0
  END as progress_percent,
  
  MIN(fe.processing_started_at) as first_file_started_at,
  MAX(fe.processing_completed_at) as last_file_completed_at,
  CASE 
    WHEN MAX(fe.processing_completed_at) IS NOT NULL AND MIN(fe.processing_started_at) IS NOT NULL THEN
      EXTRACT(EPOCH FROM (MAX(fe.processing_completed_at) - MIN(fe.processing_started_at)))::integer
    ELSE NULL
  END as total_processing_seconds,
  
  ROUND(AVG(fe.processing_duration_ms) FILTER (WHERE fe.status = 'SUCCESS') / 1000.0, 2) as avg_file_processing_seconds

FROM processing_jobs pj
-- FIX: Join on effective run_id (handles both batch_id and run_id semantics)
LEFT JOIN file_extractions fe ON COALESCE(pj.run_id, pj.batch_id) = fe.run_id
GROUP BY pj.id, pj.batch_id, pj.status, pj.zip_path, pj.total_files, pj.created_at, pj.updated_at, pj.completed_at
ORDER BY pj.created_at DESC;

-- View 2: Failed Files Report
CREATE OR REPLACE VIEW failed_files_report AS
SELECT 
  fe.run_id as batch_id,
  fe.doc_id as file_id,
  fe.filename,
  fe.file_path,
  fe.file_type,
  fe.error_type,
  fe.error,
  fe.retry_count,
  fe.processing_started_at,
  fe.processing_completed_at,
  fe.processing_duration_ms,
  fe.created_at,
  pj.batch_status,
  pj.zip_path
FROM file_extractions fe
JOIN (
  SELECT batch_id, status as batch_status, zip_path 
  FROM processing_jobs
) pj ON fe.run_id = pj.batch_id
WHERE fe.status = 'FAILED'
ORDER BY fe.processing_completed_at DESC;

-- View 3: Processing Performance Metrics
CREATE OR REPLACE VIEW processing_performance_metrics AS
SELECT 
  DATE_TRUNC('day', fe.processing_completed_at) as processing_date,
  COUNT(*) as total_files_processed,
  COUNT(*) FILTER (WHERE fe.status = 'SUCCESS') as successful_files,
  COUNT(*) FILTER (WHERE fe.status = 'FAILED') as failed_files,
  ROUND(AVG(fe.processing_duration_ms) / 1000.0, 2) as avg_processing_seconds,
  ROUND(MIN(fe.processing_duration_ms) / 1000.0, 2) as min_processing_seconds,
  ROUND(MAX(fe.processing_duration_ms) / 1000.0, 2) as max_processing_seconds,
  COUNT(*) FILTER (WHERE fe.retry_count > 0) as files_with_retries,
  ROUND(AVG(fe.retry_count), 2) as avg_retry_count,
  
  COUNT(*) FILTER (WHERE fe.error_type = 'RETRYABLE') as errors_retryable,
  COUNT(*) FILTER (WHERE fe.error_type = 'PERMANENT') as errors_permanent,
  COUNT(*) FILTER (WHERE fe.error_type = 'TIMEOUT') as errors_timeout,
  COUNT(*) FILTER (WHERE fe.error_type = 'RATE_LIMIT') as errors_rate_limit,
  COUNT(*) FILTER (WHERE fe.error_type = 'PARSE_ERROR') as errors_parse,
  COUNT(*) FILTER (WHERE fe.error_type = 'LLM_ERROR') as errors_llm

FROM file_extractions fe
WHERE fe.processing_completed_at IS NOT NULL
GROUP BY DATE_TRUNC('day', fe.processing_completed_at)
ORDER BY processing_date DESC;

-- View 4: Active Batches Monitor
CREATE OR REPLACE VIEW active_batches_monitor AS
SELECT 
  pj.batch_id,
  pj.status as batch_status,
  pj.total_files,
  COUNT(fe.id) FILTER (WHERE fe.status = 'SUCCESS') as completed_files,
  COUNT(fe.id) FILTER (WHERE fe.status = 'processing') as processing_files,
  COUNT(fe.id) FILTER (WHERE fe.status = 'FAILED') as failed_files,
  ROUND((COUNT(fe.id) FILTER (WHERE fe.status IN ('SUCCESS', 'FAILED'))::numeric / NULLIF(pj.total_files, 0)::numeric) * 100, 2) as progress_percent,
  pj.created_at,
  now() - pj.created_at as elapsed_time,
  
  ARRAY_AGG(fe.filename) FILTER (WHERE fe.status = 'processing') as current_files

FROM processing_jobs pj
LEFT JOIN file_extractions fe ON pj.batch_id = fe.run_id
WHERE pj.status IN ('queued', 'extracting', 'processing')
GROUP BY pj.id, pj.batch_id, pj.status, pj.total_files, pj.created_at
ORDER BY pj.created_at DESC;

-- View 5: Batch History Summary
CREATE OR REPLACE VIEW batch_history_summary AS
SELECT 
  pj.batch_id,
  pj.status,
  pj.total_files,
  COUNT(fe.id) FILTER (WHERE fe.status = 'SUCCESS') as files_success,
  COUNT(fe.id) FILTER (WHERE fe.status = 'FAILED') as files_failed,
  pj.created_at as started_at,
  pj.completed_at,
  EXTRACT(EPOCH FROM (pj.completed_at - pj.created_at))::integer as total_duration_seconds,
  
  EXISTS(SELECT 1 FROM run_summaries rs WHERE rs.run_id = pj.batch_id) as has_summary,
  
  pj.error_message

FROM processing_jobs pj
LEFT JOIN file_extractions fe ON pj.batch_id = fe.run_id
WHERE pj.status IN ('completed', 'completed_with_errors', 'failed')
GROUP BY pj.id, pj.batch_id, pj.status, pj.total_files, pj.created_at, pj.completed_at, pj.error_message
ORDER BY pj.completed_at DESC;

-- Grant permissions on views
GRANT SELECT ON batch_status_summary TO public;
GRANT SELECT ON failed_files_report TO public;
GRANT SELECT ON processing_performance_metrics TO public;
GRANT SELECT ON active_batches_monitor TO public;
GRANT SELECT ON batch_history_summary TO public;

-- ====================================================================
-- 005: CREATE system_alerts TABLE AND error_summary_by_type VIEW
-- ====================================================================

CREATE TABLE IF NOT EXISTS system_alerts (
  id SERIAL PRIMARY KEY,
  alert_type VARCHAR(50) NOT NULL,
  severity VARCHAR(20) NOT NULL,
  message TEXT NOT NULL,
  context JSONB,
  created_at TIMESTAMP DEFAULT now(),
  resolved_at TIMESTAMP,
  resolved_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_system_alerts_severity
  ON system_alerts(severity, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_alerts_unresolved
  ON system_alerts(resolved_at)
  WHERE resolved_at IS NULL;

-- View: error_summary_by_type
CREATE OR REPLACE VIEW error_summary_by_type AS
SELECT
  fe.error_type,
  COUNT(*) as total_errors,
  COUNT(DISTINCT fe.run_id) as batches_affected,
  ROUND(AVG(fe.retry_count), 2) as avg_retry_count,
  MIN(fe.processing_completed_at) as first_occurrence,
  MAX(fe.processing_completed_at) as last_occurrence
FROM file_extractions fe
WHERE fe.status = 'FAILED' AND fe.error_type IS NOT NULL
GROUP BY fe.error_type
ORDER BY total_errors DESC;

GRANT SELECT ON error_summary_by_type TO public;
GRANT SELECT, INSERT, UPDATE ON system_alerts TO public;

-- ====================================================================
-- VERIFICATION SUMMARY
-- ====================================================================
-- After running this migration, verify with:
-- 
-- SELECT tablename FROM pg_tables WHERE schemaname = 'public';
--   => Should show: file_extractions, run_summaries, processing_jobs, system_alerts
--
-- SELECT viewname FROM pg_views WHERE schemaname = 'public';
--   => Should show: batch_status_summary, failed_files_report, processing_performance_metrics, 
--                   active_batches_monitor, batch_history_summary, error_summary_by_type
