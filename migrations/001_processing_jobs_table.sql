/*
  Migration: 001_processing_jobs_table
  Description: Create processing_jobs table for batch-level tracking
  Author: System
  Date: 2026-01-22
  
  Purpose:
  - Track batch-level processing state
  - Store ZIP file path and metadata
  - Monitor batch progress (total/success/failed files)
  - Link batches to run_id (optional N8N execution ID)
*/

-- Create processing_jobs table
CREATE TABLE IF NOT EXISTS processing_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id text UNIQUE NOT NULL,
  zip_path text NOT NULL,
  run_id text,  -- Optional: N8N execution ID or backend job ID
  total_files integer NOT NULL DEFAULT 0,
  uploaded_by text,  -- Optional: User ID who uploaded
  status text NOT NULL DEFAULT 'pending',
  -- Status values: 'pending', 'queued', 'extracting', 'processing', 'completed', 'completed_with_errors', 'failed'
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

-- Add comments for documentation
COMMENT ON TABLE processing_jobs IS 'Tracks batch-level processing state for uploaded ZIP files';
COMMENT ON COLUMN processing_jobs.batch_id IS 'Unique identifier for the batch (e.g., batch_abc123)';
COMMENT ON COLUMN processing_jobs.zip_path IS 'File path to uploaded ZIP in shared volume (e.g., /shared/uploads/batch_abc123.zip)';
COMMENT ON COLUMN processing_jobs.run_id IS 'Optional execution/run ID from orchestrator';
COMMENT ON COLUMN processing_jobs.total_files IS 'Total number of files in the batch (set after ZIP extraction)';
COMMENT ON COLUMN processing_jobs.status IS 'Current status of batch processing';

-- Create indexes for performance
CREATE INDEX idx_processing_jobs_batch_id ON processing_jobs(batch_id);
CREATE INDEX idx_processing_jobs_status ON processing_jobs(status);
CREATE INDEX idx_processing_jobs_created_at ON processing_jobs(created_at DESC);
CREATE INDEX idx_processing_jobs_status_created ON processing_jobs(status, created_at DESC);

-- Create function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_processing_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update updated_at
DROP TRIGGER IF EXISTS trigger_update_processing_jobs_updated_at ON processing_jobs;
CREATE TRIGGER trigger_update_processing_jobs_updated_at
  BEFORE UPDATE ON processing_jobs
  FOR EACH ROW
  EXECUTE FUNCTION update_processing_jobs_updated_at();

-- Grant permissions (for Supabase RLS - adjust as needed)
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;

-- Allow public access for demo (change for production)
CREATE POLICY "Public can view processing jobs"
  ON processing_jobs FOR SELECT
  TO public
  USING (true);

CREATE POLICY "Public can insert processing jobs"
  ON processing_jobs FOR INSERT
  TO public
  WITH CHECK (true);

CREATE POLICY "Public can update processing jobs"
  ON processing_jobs FOR UPDATE
  TO public
  USING (true);

-- Verification query (uncomment to test)
-- SELECT table_name, column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'processing_jobs'
-- ORDER BY ordinal_position;
