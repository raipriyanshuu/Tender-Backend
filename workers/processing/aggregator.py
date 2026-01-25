from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from workers.config import Config
from workers.database import operations
from workers.database.models import FileExtraction, RunSummary


def _merge_dicts(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for chunk in chunks:
        for key, value in chunk.items():
            if key not in merged:
                merged[key] = value
                continue

            if isinstance(value, list) and isinstance(merged[key], list):
                merged[key] = merged[key] + [item for item in value if item not in merged[key]]
                continue

            if isinstance(value, dict) and isinstance(merged[key], dict):
                for nested_key, nested_value in value.items():
                    if merged[key].get(nested_key) in (None, "", []):
                        merged[key][nested_key] = nested_value
                continue

            if merged[key] in (None, "", []):
                merged[key] = value

    return merged


def aggregate_batch(session: Session, batch_id: str, config: Config) -> RunSummary:
    import logging
    logger = logging.getLogger("worker.aggregator")
    logger.info(f"[Aggregator] START: aggregate_batch for {batch_id}")
    
    stats = operations.get_batch_statistics(session, batch_id)
    logger.info(f"[Aggregator] Stats: {stats}")
    
    files = operations.get_batch_files(session, batch_id)
    logger.info(f"[Aggregator] Found {len(files)} files for batch {batch_id}")

    extracted_payloads = [
        file.extracted_json
        for file in files
        if file.status == FileExtraction.STATUS_SUCCESS and file.extracted_json
    ]

    ui_json = _merge_dicts(extracted_payloads)
    summary_json = {
        "batch_id": batch_id,
        "run_id": stats["run_id"],
        "total_files": stats["total_files"],
        "success_files": stats["success_files"],
        "failed_files": stats["failed_files"],
    }

    status = (
        RunSummary.STATUS_COMPLETED
        if stats["success_files"] > 0
        else RunSummary.STATUS_FAILED
    )

    logger.info(f"[Aggregator] Creating/updating run_summary for run_id={stats['run_id']}")
    
    summary = operations.create_or_update_run_summary(
        session,
        stats["run_id"],
        ui_json,
        summary_json=summary_json,
        status=status,
    )
    summary.total_files = stats["total_files"]
    summary.success_files = stats["success_files"]
    summary.failed_files = stats["failed_files"]
    
    logger.info(f"[Aggregator] run_summary created/updated, flushing to DB")
    
    # Flush to ensure run_summaries row is persisted
    session.flush()
    
    logger.info(f"[Aggregator] COMPLETE: aggregate_batch for {batch_id}")
    return summary
