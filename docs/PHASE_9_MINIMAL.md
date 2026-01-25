# Phase 9 - Aggregation (Minimal)

## Goal
Aggregate per-file `extracted_json` into a single `run_summaries` record for the batch.

## What It Does
- Collects all successful `file_extractions` for the batch
- Merges JSON payloads into one `ui_json`
- Stores summary counts in `summary_json`
- Writes `run_summaries` with totals, success, failed counts

## Trigger
- Backend orchestrator calls the worker endpoint after batch processing completes.

## API
- `POST /aggregate-batch` (worker)
- `GET /api/batches/:batchId/summary` (backend)

## Notes
- No Phase 8 progress tracking required.
- Database remains the source of truth.
