from __future__ import annotations

import shutil
import signal
import sys

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from workers.config import load_config
from workers.database.connection import get_session, test_connection
from workers.processing.aggregator import aggregate_batch
from workers.processing.extractor import process_file

app = FastAPI(title="Tender Worker API")

# Graceful shutdown handler
def shutdown_handler(sig, frame):
    print(f"\nReceived signal {sig}, shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


class ProcessFileRequest(BaseModel):
    doc_id: str


class AggregateBatchRequest(BaseModel):
    batch_id: str


@app.get("/health")
def health_check():
    try:
        config = load_config()
        test_connection(config)
        disk = shutil.disk_usage(config.storage_base_path)
        disk_usage_percent = round((disk.used / disk.total) * 100, 2) if disk.total else 0

        try:
            import PyPDF2  # noqa: F401
            from docx import Document  # noqa: F401
            from openpyxl import load_workbook  # noqa: F401
            parsers_ready = True
        except Exception:
            parsers_ready = False

        llm_configured = bool(config.openai_api_key) and config.openai_api_key != "your_openai_api_key_here"
        llm_status = "ok" if llm_configured else "missing_or_invalid_api_key"

        return {
            "status": "ok" if llm_configured else "degraded",
            "checks": {
                "database": "ok",
                "storage_path": config.storage_base_path,
                "disk_usage_percent": disk_usage_percent,
                "parsers_ready": parsers_ready,
                "llm_configured": llm_configured,
                "llm_status": llm_status,
            },
        }
    except Exception as exc:  # noqa: BLE001 - surface health issues
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/process-file")
def process_file_endpoint(payload: ProcessFileRequest):
    config = load_config()
    try:
        with get_session(config) as session:
            process_file(session, payload.doc_id, config)
        return {"success": True, "doc_id": payload.doc_id}
    except Exception as exc:  # noqa: BLE001 - surface infrastructure errors only
        import traceback
        error_detail = f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}"
        print(f"INFRASTRUCTURE ERROR processing {payload.doc_id}: {error_detail}")
        # Only infrastructure errors (DB connection, etc.) should reach here
        # Processing errors are caught in extractor and marked as FAILED
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/aggregate-batch")
def aggregate_batch_endpoint(payload: AggregateBatchRequest):
    config = load_config()
    try:
        with get_session(config) as session:
            aggregate_batch(session, payload.batch_id, config)
        return {"success": True, "batch_id": payload.batch_id}
    except Exception as exc:  # noqa: BLE001 - surface processing errors
        raise HTTPException(status_code=500, detail=str(exc)) from exc
