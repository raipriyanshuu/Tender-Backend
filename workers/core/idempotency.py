from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from workers.core.logging import setup_logger
from workers.database.models import FileExtraction


def ensure_idempotent_file(
    session: Session,
    doc_id: str,
    defaults: dict,
) -> Tuple[FileExtraction, bool]:
    existing = (
        session.query(FileExtraction)
        .filter(FileExtraction.doc_id == doc_id)
        .one_or_none()
    )
    if existing:
        return existing, False

    try:
        created = FileExtraction(doc_id=doc_id, **defaults)
        session.add(created)
        return created, True
    except IntegrityError:
        session.rollback()
        existing = (
            session.query(FileExtraction)
            .filter(FileExtraction.doc_id == doc_id)
            .one_or_none()
        )
        if existing:
            return existing, False
        raise


def should_reprocess_file(
    file_extraction: FileExtraction,
    max_retry_attempts: int,
    stale_seconds: int = 1800,
) -> bool:
    if file_extraction.status == FileExtraction.STATUS_SUCCESS:
        return False

    if (
        file_extraction.status == FileExtraction.STATUS_FAILED
        and file_extraction.error_type == FileExtraction.ERROR_PERMANENT
    ):
        return False

    if (
        file_extraction.status == FileExtraction.STATUS_FAILED
        and (file_extraction.retry_count or 0) < max_retry_attempts
    ):
        return True

    if file_extraction.status in {
        FileExtraction.STATUS_PENDING,
        FileExtraction.STATUS_PROCESSING,
    }:
        if file_extraction.processing_started_at is None:
            return True
        elapsed = datetime.now(timezone.utc) - file_extraction.processing_started_at
        return elapsed.total_seconds() > stale_seconds

    return False
