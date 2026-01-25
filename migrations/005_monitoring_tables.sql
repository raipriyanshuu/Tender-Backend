/*
  Migration: 005_monitoring_tables
  Description: Add monitoring tables and views
  Author: System
  Date: 2026-01-22
*/

-- Table: system_alerts
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

COMMENT ON VIEW error_summary_by_type IS 'Aggregate error counts by error_type';

-- Grant permissions
GRANT SELECT ON error_summary_by_type TO public;
GRANT SELECT, INSERT, UPDATE ON system_alerts TO public;
