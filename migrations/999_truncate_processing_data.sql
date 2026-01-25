-- WARNING: This will DELETE all processing data.
-- Use only for local reset/testing.

BEGIN;

TRUNCATE TABLE
  file_extractions,
  run_summaries,
  processing_jobs,
  system_alerts
RESTART IDENTITY CASCADE;

COMMIT;
