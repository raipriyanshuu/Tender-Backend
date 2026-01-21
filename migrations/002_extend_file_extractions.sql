/*
  Migration: 002_extend_file_extractions
  Description: Extend existing file_extractions table with processing metadata
  Author: System
  Date: 2026-01-22
  
  Purpose:
  - Add timing columns for performance tracking
  - Add retry tracking columns
  - Add error classification
  - Add file_path for local filesystem reference
  - Add indexes for batch status queries
*/

-- Add new columns to file_extractions table
ALTER TABLE file_extractions 
  ADD COLUMN IF NOT EXISTS file_path text,
  ADD COLUMN IF NOT EXISTS processing_started_at timestamptz,
  ADD COLUMN IF NOT EXISTS processing_completed_at timestamptz,
  ADD COLUMN IF NOT EXISTS processing_duration_ms integer,
  ADD COLUMN IF NOT EXISTS retry_count integer DEFAULT 0,
  ADD COLUMN IF NOT EXISTS error_type text;
  -- error_type values: 'RETRYABLE', 'PERMANENT', 'TIMEOUT', 'RATE_LIMIT', 'PARSE_ERROR', 'LLM_ERROR'

-- Add comments for documentation
COMMENT ON COLUMN file_extractions.file_path IS 'Local filesystem path to file in shared volume (e.g., /shared/extracted/batch_abc123/file_001.pdf)';
COMMENT ON COLUMN file_extractions.processing_started_at IS 'Timestamp when worker started processing this file';
COMMENT ON COLUMN file_extractions.processing_completed_at IS 'Timestamp when worker completed processing (success or failure)';
COMMENT ON COLUMN file_extractions.processing_duration_ms IS 'Total processing time in milliseconds';
COMMENT ON COLUMN file_extractions.retry_count IS 'Number of retry attempts (0 = first attempt)';
COMMENT ON COLUMN file_extractions.error_type IS 'Classification of error if status is FAILED';

-- Create additional indexes for batch queries
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

-- Create index on doc_id if it doesn't exist (for idempotency checks)
CREATE UNIQUE INDEX IF NOT EXISTS idx_file_extractions_doc_id_unique 
  ON file_extractions(doc_id);

-- Add check constraint for status values
ALTER TABLE file_extractions 
  DROP CONSTRAINT IF EXISTS check_file_extractions_status;

ALTER TABLE file_extractions 
  ADD CONSTRAINT check_file_extractions_status 
  CHECK (status IN ('pending', 'processing', 'SUCCESS', 'FAILED', 'SKIPPED'));

-- Add check constraint for error_type values
ALTER TABLE file_extractions 
  DROP CONSTRAINT IF EXISTS check_file_extractions_error_type;

ALTER TABLE file_extractions 
  ADD CONSTRAINT check_file_extractions_error_type 
  CHECK (error_type IS NULL OR error_type IN ('RETRYABLE', 'PERMANENT', 'TIMEOUT', 'RATE_LIMIT', 'PARSE_ERROR', 'LLM_ERROR', 'UNKNOWN'));

-- Add computed column trigger to calculate processing_duration_ms
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

-- Verification query (uncomment to test)
-- SELECT 
--   column_name, 
--   data_type, 
--   is_nullable,
--   column_default
-- FROM information_schema.columns 
-- WHERE table_name = 'file_extractions'
--   AND column_name IN ('file_path', 'processing_started_at', 'processing_completed_at', 'retry_count', 'error_type')
-- ORDER BY ordinal_position;
