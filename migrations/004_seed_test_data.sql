/*
  Migration: 004_seed_test_data
  Description: Insert test data for development and testing
  Author: System
  Date: 2026-01-22
  
  Purpose:
  - Provide sample data for testing backend and frontend
  - Validate database schema and constraints
  - Test queries and views
  
  WARNING: Only run this in development/testing environments!
  DO NOT run in production!
*/

-- Clear existing test data (if any)
DELETE FROM file_extractions WHERE run_id LIKE 'test_batch_%';
DELETE FROM run_summaries WHERE run_id LIKE 'test_batch_%';
DELETE FROM processing_jobs WHERE batch_id LIKE 'test_batch_%';

-- Test Scenario 1: Completed batch with all files successful
INSERT INTO processing_jobs (
  batch_id, 
  zip_path, 
  run_id,
  total_files, 
  uploaded_by,
  status,
  created_at,
  updated_at,
  completed_at
) VALUES (
  'test_batch_001',
  '/shared/uploads/test_batch_001.zip',
  'exec_test_001',
  3,
  'test_user',
  'completed',
  now() - interval '30 minutes',
  now() - interval '5 minutes',
  now() - interval '5 minutes'
);

-- Insert test file extractions for batch 001
INSERT INTO file_extractions (
  doc_id,
  run_id,
  source,
  filename,
  file_path,
  file_type,
  status,
  extracted_json,
  processing_started_at,
  processing_completed_at,
  retry_count,
  created_at
) VALUES 
(
  'test_file_001',
  'test_batch_001',
  'local',
  'tender_document_1.pdf',
  '/shared/extracted/test_batch_001/tender_document_1.pdf',
  'application/pdf',
  'SUCCESS',
  '{"doc_meta": {"tender_id": "TEST-001", "organization": "Test Company GmbH"}, "mandatory_requirements": [{"requirement_de": "ISO 9001 Zertifizierung"}], "risks": [{"risk_de": "Vertragsstrafen bei Verzug"}]}'::jsonb,
  now() - interval '28 minutes',
  now() - interval '27 minutes',
  0,
  now() - interval '30 minutes'
),
(
  'test_file_002',
  'test_batch_001',
  'local',
  'tender_document_2.docx',
  '/shared/extracted/test_batch_001/tender_document_2.docx',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'SUCCESS',
  '{"doc_meta": {"tender_id": "TEST-001", "organization": "Test Company GmbH"}, "mandatory_requirements": [{"requirement_de": "DGUV Vorschrift 52"}], "risks": []}'::jsonb,
  now() - interval '26 minutes',
  now() - interval '25 minutes',
  0,
  now() - interval '30 minutes'
),
(
  'test_file_003',
  'test_batch_001',
  'local',
  'tender_document_3.xlsx',
  '/shared/extracted/test_batch_001/tender_document_3.xlsx',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'SUCCESS',
  '{"doc_meta": {"tender_id": "TEST-001"}, "mandatory_requirements": [], "risks": []}'::jsonb,
  now() - interval '24 minutes',
  now() - interval '23 minutes',
  0,
  now() - interval '30 minutes'
);

-- Test Scenario 2: Processing batch (in progress)
INSERT INTO processing_jobs (
  batch_id, 
  zip_path,
  run_id,
  total_files,
  uploaded_by,
  status,
  created_at,
  updated_at
) VALUES (
  'test_batch_002',
  '/shared/uploads/test_batch_002.zip',
  'exec_test_002',
  5,
  'test_user',
  'processing',
  now() - interval '10 minutes',
  now() - interval '1 minute'
);

-- Insert test files for batch 002 (some completed, some pending)
INSERT INTO file_extractions (
  doc_id,
  run_id,
  source,
  filename,
  file_path,
  file_type,
  status,
  extracted_json,
  processing_started_at,
  processing_completed_at,
  retry_count,
  created_at
) VALUES 
(
  'test_file_004',
  'test_batch_002',
  'local',
  'tender_a.pdf',
  '/shared/extracted/test_batch_002/tender_a.pdf',
  'application/pdf',
  'SUCCESS',
  '{"doc_meta": {"tender_id": "TEST-002"}}'::jsonb,
  now() - interval '9 minutes',
  now() - interval '8 minutes',
  0,
  now() - interval '10 minutes'
),
(
  'test_file_005',
  'test_batch_002',
  'local',
  'tender_b.pdf',
  '/shared/extracted/test_batch_002/tender_b.pdf',
  'application/pdf',
  'SUCCESS',
  '{"doc_meta": {"tender_id": "TEST-002"}}'::jsonb,
  now() - interval '7 minutes',
  now() - interval '6 minutes',
  0,
  now() - interval '10 minutes'
),
(
  'test_file_006',
  'test_batch_002',
  'local',
  'tender_c.pdf',
  '/shared/extracted/test_batch_002/tender_c.pdf',
  'application/pdf',
  'processing',
  '{}'::jsonb,
  now() - interval '2 minutes',
  NULL,
  0,
  now() - interval '10 minutes'
),
(
  'test_file_007',
  'test_batch_002',
  'local',
  'tender_d.pdf',
  '/shared/extracted/test_batch_002/tender_d.pdf',
  'application/pdf',
  'pending',
  '{}'::jsonb,
  NULL,
  NULL,
  0,
  now() - interval '10 minutes'
),
(
  'test_file_008',
  'test_batch_002',
  'local',
  'tender_e.pdf',
  '/shared/extracted/test_batch_002/tender_e.pdf',
  'application/pdf',
  'pending',
  '{}'::jsonb,
  NULL,
  NULL,
  0,
  now() - interval '10 minutes'
);

-- Test Scenario 3: Batch with failures
INSERT INTO processing_jobs (
  batch_id,
  zip_path,
  run_id,
  total_files,
  uploaded_by,
  status,
  created_at,
  updated_at,
  completed_at
) VALUES (
  'test_batch_003',
  '/shared/uploads/test_batch_003.zip',
  'exec_test_003',
  4,
  'test_user',
  'completed_with_errors',
  now() - interval '1 hour',
  now() - interval '30 minutes',
  now() - interval '30 minutes'
);

-- Insert test files with some failures
INSERT INTO file_extractions (
  doc_id,
  run_id,
  source,
  filename,
  file_path,
  file_type,
  status,
  extracted_json,
  error,
  error_type,
  processing_started_at,
  processing_completed_at,
  retry_count,
  created_at
) VALUES 
(
  'test_file_009',
  'test_batch_003',
  'local',
  'valid_tender.pdf',
  '/shared/extracted/test_batch_003/valid_tender.pdf',
  'application/pdf',
  'SUCCESS',
  '{"doc_meta": {"tender_id": "TEST-003"}}'::jsonb,
  NULL,
  NULL,
  now() - interval '58 minutes',
  now() - interval '57 minutes',
  0,
  now() - interval '1 hour'
),
(
  'test_file_010',
  'test_batch_003',
  'local',
  'corrupt_file.pdf',
  '/shared/extracted/test_batch_003/corrupt_file.pdf',
  'application/pdf',
  'FAILED',
  '{}'::jsonb,
  'Failed to parse PDF: corrupt file structure',
  'PARSE_ERROR',
  now() - interval '56 minutes',
  now() - interval '55 minutes',
  2,
  now() - interval '1 hour'
),
(
  'test_file_011',
  'test_batch_003',
  'local',
  'timeout_file.pdf',
  '/shared/extracted/test_batch_003/timeout_file.pdf',
  'application/pdf',
  'FAILED',
  '{}'::jsonb,
  'LLM API timeout after 120 seconds',
  'TIMEOUT',
  now() - interval '54 minutes',
  now() - interval '52 minutes',
  3,
  now() - interval '1 hour'
),
(
  'test_file_012',
  'test_batch_003',
  'local',
  'another_valid.docx',
  '/shared/extracted/test_batch_003/another_valid.docx',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'SUCCESS',
  '{"doc_meta": {"tender_id": "TEST-003"}}'::jsonb,
  NULL,
  NULL,
  now() - interval '50 minutes',
  now() - interval '49 minutes',
  0,
  now() - interval '1 hour'
);

-- Test Scenario 4: Fresh batch (just queued)
INSERT INTO processing_jobs (
  batch_id,
  zip_path,
  run_id,
  total_files,
  uploaded_by,
  status,
  created_at,
  updated_at
) VALUES (
  'test_batch_004',
  '/shared/uploads/test_batch_004.zip',
  NULL,
  0,
  'test_user',
  'queued',
  now() - interval '30 seconds',
  now() - interval '30 seconds'
);

-- Verification queries
SELECT '=== Test Data Summary ===' as message;

SELECT 
  'Processing Jobs' as table_name,
  COUNT(*) as record_count,
  COUNT(*) FILTER (WHERE status = 'completed') as completed,
  COUNT(*) FILTER (WHERE status = 'processing') as processing,
  COUNT(*) FILTER (WHERE status = 'queued') as queued
FROM processing_jobs 
WHERE batch_id LIKE 'test_batch_%';

SELECT 
  'File Extractions' as table_name,
  COUNT(*) as record_count,
  COUNT(*) FILTER (WHERE status = 'SUCCESS') as success,
  COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
  COUNT(*) FILTER (WHERE status = 'processing') as processing,
  COUNT(*) FILTER (WHERE status = 'pending') as pending
FROM file_extractions 
WHERE run_id LIKE 'test_batch_%';

-- Test views
SELECT '=== Testing batch_status_summary view ===' as message;
SELECT * FROM batch_status_summary WHERE batch_id LIKE 'test_batch_%';

SELECT '=== Testing failed_files_report view ===' as message;
SELECT * FROM failed_files_report WHERE batch_id LIKE 'test_batch_%';

SELECT '=== Testing active_batches_monitor view ===' as message;
SELECT * FROM active_batches_monitor WHERE batch_id LIKE 'test_batch_%';

-- Success message
SELECT '✅ Test data inserted successfully!' as message;
SELECT 'Run the following queries to explore:' as hint;
SELECT '  SELECT * FROM batch_status_summary;' as query_1;
SELECT '  SELECT * FROM failed_files_report;' as query_2;
SELECT '  SELECT * FROM active_batches_monitor;' as query_3;
