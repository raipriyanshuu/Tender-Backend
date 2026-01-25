# Phase 10: Frontend Integration (Small Doc)

## Goal
Connect the fixed frontend UI to the backend batch pipeline without changing UI contracts.

## What Was Added
- Upload `.zip` to backend and receive `batch_id`.
- Trigger processing via `/api/batches/:batchId/process`.
- Poll `/api/batches/:batchId/status` for progress (DB polling).
- Fetch summary from `/api/batches/:batchId/summary`.
- Map aggregated `ui_json` to existing `Tender` UI shape.

## Key Endpoints
- `POST /upload-tender`
- `POST /api/batches/:batchId/process`
- `GET /api/batches/:batchId/status`
- `GET /api/batches/:batchId/summary`

## Why It Matters
This phase makes the backend workflow visible to users, enabling upload → progress → results with no UI redesign.
