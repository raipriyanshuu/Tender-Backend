/*
  Migration 006: Fix batch_status_summary view join condition
  
  Problem: The view joins on pj.batch_id = fe.run_id, but this doesn't work
  when processing_jobs.run_id is set to a different value than batch_id.
  
  Solution: Join on COALESCE(pj.run_id, pj.batch_id) = fe.run_id
  This matches the _resolve_run_id() logic in Python operations.
*/

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

COMMENT ON VIEW batch_status_summary IS 'Real-time batch processing status with file counts and progress (fixed join condition)';
