/*
  # Create N8N Integration Tables
  
  This migration creates the tables that the N8N workflow writes to:
  - file_extractions: Stores extraction results for each processed file
  - run_summaries: Stores aggregated UI-ready data for each N8N run
  
  These tables are populated by the N8N workflow after processing tender documents with LLM.
*/

-- Create file_extractions table
CREATE TABLE IF NOT EXISTS file_extractions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id text NOT NULL,
  source text NOT NULL DEFAULT 'gdrive',
  doc_id text NOT NULL UNIQUE,
  filename text NOT NULL,
  file_type text,
  extracted_json jsonb DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending',
  error text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Create run_summaries table
CREATE TABLE IF NOT EXISTS run_summaries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id text NOT NULL UNIQUE,
  summary_json jsonb DEFAULT '{}'::jsonb,
  ui_json jsonb DEFAULT '{}'::jsonb,
  total_files integer DEFAULT 0,
  success_files integer DEFAULT 0,
  failed_files integer DEFAULT 0,
  status text NOT NULL DEFAULT 'pending',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_file_extractions_run_id ON file_extractions(run_id);
CREATE INDEX IF NOT EXISTS idx_file_extractions_status ON file_extractions(status);
CREATE INDEX IF NOT EXISTS idx_file_extractions_doc_id ON file_extractions(doc_id);

CREATE INDEX IF NOT EXISTS idx_run_summaries_run_id ON run_summaries(run_id);
CREATE INDEX IF NOT EXISTS idx_run_summaries_status ON run_summaries(status);

-- GIN indexes for JSONB fields for efficient querying
CREATE INDEX IF NOT EXISTS idx_file_extractions_json ON file_extractions USING gin(extracted_json);
CREATE INDEX IF NOT EXISTS idx_run_summaries_ui_json ON run_summaries USING gin(ui_json);
CREATE INDEX IF NOT EXISTS idx_run_summaries_summary_json ON run_summaries USING gin(summary_json);

-- Enable Row Level Security
ALTER TABLE file_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE run_summaries ENABLE ROW LEVEL SECURITY;

-- RLS Policies - Allow public access for demo purposes
-- In production, restrict to authenticated users
CREATE POLICY "Public can view file extractions"
  ON file_extractions FOR SELECT
  TO public
  USING (true);

CREATE POLICY "Public can insert file extractions"
  ON file_extractions FOR INSERT
  TO public
  WITH CHECK (true);

CREATE POLICY "Public can update file extractions"
  ON file_extractions FOR UPDATE
  TO public
  USING (true);

CREATE POLICY "Public can view run summaries"
  ON run_summaries FOR SELECT
  TO public
  USING (true);

CREATE POLICY "Public can insert run summaries"
  ON run_summaries FOR INSERT
  TO public
  WITH CHECK (true);

CREATE POLICY "Public can update run summaries"
  ON run_summaries FOR UPDATE
  TO public
  USING (true);

-- Function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to auto-update updated_at
DROP TRIGGER IF EXISTS update_file_extractions_updated_at ON file_extractions;
CREATE TRIGGER update_file_extractions_updated_at
  BEFORE UPDATE ON file_extractions
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_run_summaries_updated_at ON run_summaries;
CREATE TRIGGER update_run_summaries_updated_at
  BEFORE UPDATE ON run_summaries
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
