/*
  Migration: 003_database_views
  Description: Create database views for common queries
  Author: System
  Date: 2026-01-22
  
  Purpose:
  - Simplify batch status queries
  - Provide pre-aggregated data for monitoring
  - Improve query performance for common patterns
*/

-- View 1: Batch Status Summary
-- Provides real-time batch processing status with file counts
CREATE OR REPLACE VIEW batch_status_summary AS
SELECT 
  pj.batch_id,
  pj.status as batch_status,
  pj.zip_path,
  pj.total_files,
  pj.created_at as batch_created_at,
  pj.updated_at as batch_updated_at,
  pj.completed_at as batch_completed_at,
  
  -- File counts from file_extractions
  COUNT(fe.id) as files_tracked,
  COUNT(fe.id) FILTER (WHERE fe.status = 'SUCCESS') as files_success,
  COUNT(fe.id) FILTER (WHERE fe.status = 'FAILED') as files_failed,
  COUNT(fe.id) FILTER (WHERE fe.status = 'processing') as files_processing,
  COUNT(fe.id) FILTER (WHERE fe.status = 'pending') as files_pending,
  
  -- Progress calculation
  CASE 
    WHEN pj.total_files > 0 THEN 
      ROUND((COUNT(fe.id) FILTER (WHERE fe.status IN ('SUCCESS', 'FAILED'))::numeric / pj.total_files::numeric) * 100, 2)
    ELSE 0
  END as progress_percent,
  
  -- Timing statistics
  MIN(fe.processing_started_at) as first_file_started_at,
  MAX(fe.processing_completed_at) as last_file_completed_at,
  CASE 
    WHEN MAX(fe.processing_completed_at) IS NOT NULL AND MIN(fe.processing_started_at) IS NOT NULL THEN
      EXTRACT(EPOCH FROM (MAX(fe.processing_completed_at) - MIN(fe.processing_started_at)))::integer
    ELSE NULL
  END as total_processing_seconds,
  
  -- Average processing time per file (in seconds)
  ROUND(AVG(fe.processing_duration_ms) FILTER (WHERE fe.status = 'SUCCESS') / 1000.0, 2) as avg_file_processing_seconds

FROM processing_jobs pj
-- FIX: Join on effective run_id (handles both batch_id and run_id semantics)
LEFT JOIN file_extractions fe ON COALESCE(pj.run_id, pj.batch_id) = fe.run_id
GROUP BY pj.id, pj.batch_id, pj.status, pj.zip_path, pj.total_files, pj.created_at, pj.updated_at, pj.completed_at
ORDER BY pj.created_at DESC;

COMMENT ON VIEW batch_status_summary IS 'Real-time batch processing status with file counts and progress';

-- View 2: Failed Files Report
-- Lists all failed files with error details for debugging
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

COMMENT ON VIEW failed_files_report IS 'List of all failed file processing attempts with error details';

-- View 3: Processing Performance Metrics
-- Provides performance statistics for monitoring
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
  
  -- Error type distribution
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

COMMENT ON VIEW processing_performance_metrics IS 'Daily performance metrics and error statistics';

-- View 4: Active Batches Monitor
-- Shows currently processing batches for monitoring
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
  
  -- List of currently processing files
  ARRAY_AGG(fe.filename) FILTER (WHERE fe.status = 'processing') as current_files

FROM processing_jobs pj
LEFT JOIN file_extractions fe ON pj.batch_id = fe.run_id
WHERE pj.status IN ('queued', 'extracting', 'processing')
GROUP BY pj.id, pj.batch_id, pj.status, pj.total_files, pj.created_at
ORDER BY pj.created_at DESC;

COMMENT ON VIEW active_batches_monitor IS 'Currently active/processing batches with real-time progress';

-- View 5: Batch History Summary
-- Historical view of completed batches
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
  
  -- Check if there's a summary in run_summaries
  EXISTS(SELECT 1 FROM run_summaries rs WHERE rs.run_id = pj.batch_id) as has_summary,
  
  -- Error summary
  pj.error_message

FROM processing_jobs pj
LEFT JOIN file_extractions fe ON pj.batch_id = fe.run_id
WHERE pj.status IN ('completed', 'completed_with_errors', 'failed')
GROUP BY pj.id, pj.batch_id, pj.status, pj.total_files, pj.created_at, pj.completed_at, pj.error_message
ORDER BY pj.completed_at DESC;

COMMENT ON VIEW batch_history_summary IS 'Historical record of completed batches';

-- Grant SELECT permissions on views
GRANT SELECT ON batch_status_summary TO public;
GRANT SELECT ON failed_files_report TO public;
GRANT SELECT ON processing_performance_metrics TO public;
GRANT SELECT ON active_batches_monitor TO public;
GRANT SELECT ON batch_history_summary TO public;

-- Verification queries (uncomment to test)
-- SELECT * FROM batch_status_summary LIMIT 5;
-- SELECT * FROM failed_files_report LIMIT 5;
-- SELECT * FROM processing_performance_metrics LIMIT 5;
-- SELECT * FROM active_batches_monitor LIMIT 5;
-- SELECT * FROM batch_history_summary LIMIT 5;
