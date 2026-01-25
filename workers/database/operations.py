from __future__ import annotations

from typing import Iterable, Tuple

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import text

from workers.database.models import FileExtraction, ProcessingJob, RunSummary


def get_batch_by_id(session: Session, batch_id: str) -> ProcessingJob | None:
    return (
        session.query(ProcessingJob)
        .filter(ProcessingJob.batch_id == batch_id)
        .one_or_none()
    )


def update_batch_status(
    session: Session,
    batch_id: str,
    status: str,
    error_message: str | None = None,
) -> ProcessingJob:
    job = get_batch_by_id(session, batch_id)
    if job is None:
        raise ValueError(f"Batch not found: {batch_id}")
    job.status = status
    if error_message:
        job.error_message = error_message
    return job


def _resolve_run_id(job: ProcessingJob) -> str:
    return job.run_id or job.batch_id


def get_batch_files(session: Session, batch_id: str) -> list[FileExtraction]:
    job = get_batch_by_id(session, batch_id)
    if job is None:
        raise ValueError(f"Batch not found: {batch_id}")
    run_id = _resolve_run_id(job)
    files = (
        session.query(FileExtraction)
        .filter(FileExtraction.run_id == run_id)
        .order_by(FileExtraction.created_at.desc())
        .all()
    )
    if not files and job.run_id and job.run_id != job.batch_id:
        files = (
            session.query(FileExtraction)
            .filter(FileExtraction.run_id == job.batch_id)
            .order_by(FileExtraction.created_at.desc())
            .all()
        )
    return files


def mark_batch_completed(session: Session, batch_id: str) -> ProcessingJob:
    job = update_batch_status(session, batch_id, ProcessingJob.STATUS_COMPLETED)
    job.completed_at = func.now()
    return job


def mark_batch_failed(session: Session, batch_id: str, error_message: str) -> ProcessingJob:
    job = update_batch_status(session, batch_id, ProcessingJob.STATUS_FAILED, error_message)
    job.completed_at = func.now()
    return job


def create_file_extraction(
    session: Session,
    run_id: str,
    file_info: dict,
) -> FileExtraction:
    file_extraction = FileExtraction(run_id=run_id, **file_info)
    session.add(file_extraction)
    return file_extraction


def get_file_by_doc_id(session: Session, doc_id: str) -> FileExtraction | None:
    return (
        session.query(FileExtraction)
        .filter(FileExtraction.doc_id == doc_id)
        .one_or_none()
    )


def update_file_status(session: Session, doc_id: str, status: str) -> FileExtraction:
    file_extraction = get_file_by_doc_id(session, doc_id)
    if file_extraction is None:
        raise ValueError(f"File not found: {doc_id}")
    file_extraction.status = status
    return file_extraction


def mark_file_processing_start(session: Session, doc_id: str) -> FileExtraction:
    file_extraction = update_file_status(session, doc_id, FileExtraction.STATUS_PROCESSING)
    file_extraction.processing_started_at = func.now()
    return file_extraction


def mark_file_success(
    session: Session,
    doc_id: str,
    extracted_json: dict,
) -> FileExtraction:
    file_extraction = update_file_status(session, doc_id, FileExtraction.STATUS_SUCCESS)
    file_extraction.extracted_json = extracted_json
    file_extraction.processing_completed_at = func.now()
    file_extraction.error = None
    file_extraction.error_type = None
    return file_extraction


def mark_file_failed(
    session: Session,
    doc_id: str,
    error_message: str,
    error_type: str,
) -> FileExtraction:
    file_extraction = update_file_status(session, doc_id, FileExtraction.STATUS_FAILED)
    file_extraction.processing_completed_at = func.now()
    file_extraction.error = error_message
    file_extraction.error_type = error_type
    return file_extraction


def increment_retry_count(session: Session, doc_id: str) -> int:
    file_extraction = get_file_by_doc_id(session, doc_id)
    if file_extraction is None:
        raise ValueError(f"File not found: {doc_id}")
    current = file_extraction.retry_count or 0
    file_extraction.retry_count = current + 1
    return file_extraction.retry_count


def is_batch_already_processed(session: Session, batch_id: str) -> bool:
    job = get_batch_by_id(session, batch_id)
    if job is None:
        return False
    return job.status in {
        ProcessingJob.STATUS_COMPLETED,
        ProcessingJob.STATUS_COMPLETED_WITH_ERRORS,
    }


def is_file_already_processed(session: Session, doc_id: str) -> bool:
    file_extraction = get_file_by_doc_id(session, doc_id)
    if file_extraction is None:
        return False
    return file_extraction.status == FileExtraction.STATUS_SUCCESS


def get_or_create_file_extraction(
    session: Session,
    doc_id: str,
    defaults: dict,
) -> Tuple[FileExtraction, bool]:
    existing = get_file_by_doc_id(session, doc_id)
    if existing:
        return existing, False
    try:
        created = FileExtraction(doc_id=doc_id, **defaults)
        session.add(created)
        return created, True
    except IntegrityError:
        session.rollback()
        existing = get_file_by_doc_id(session, doc_id)
        if existing:
            return existing, False
        raise


def get_batch_statistics(session: Session, batch_id: str) -> dict:
    job = get_batch_by_id(session, batch_id)
    if job is None:
        raise ValueError(f"Batch not found: {batch_id}")
    run_id = _resolve_run_id(job)

    totals = (
        session.query(
            func.count(FileExtraction.id).label("total"),
            func.sum(
                case(
                    (FileExtraction.status == FileExtraction.STATUS_SUCCESS, 1),
                    else_=0,
                )
            ).label("success"),
            func.sum(
                case(
                    (FileExtraction.status == FileExtraction.STATUS_FAILED, 1),
                    else_=0,
                )
            ).label("failed"),
        )
        .filter(FileExtraction.run_id == run_id)
        .one()
    )

    total = totals.total or 0
    success = totals.success or 0
    failed = totals.failed or 0

    if total == 0 and job.run_id and job.run_id != job.batch_id:
        fallback = (
            session.query(
                func.count(FileExtraction.id).label("total"),
                func.sum(
                    case(
                        (FileExtraction.status == FileExtraction.STATUS_SUCCESS, 1),
                        else_=0,
                    )
                ).label("success"),
                func.sum(
                    case(
                        (FileExtraction.status == FileExtraction.STATUS_FAILED, 1),
                        else_=0,
                    )
                ).label("failed"),
            )
            .filter(FileExtraction.run_id == job.batch_id)
            .one()
        )
        total = fallback.total or 0
        success = fallback.success or 0
        failed = fallback.failed or 0
        run_id = job.batch_id

    return {
        "batch_id": batch_id,
        "run_id": run_id,
        "total_files": total,
        "success_files": success,
        "failed_files": failed,
    }


def get_batch_state_counts(session: Session, batch_id: str) -> dict:
    job = get_batch_by_id(session, batch_id)
    if job is None:
        raise ValueError(f"Batch not found: {batch_id}")
    run_id = _resolve_run_id(job)

    totals = (
        session.query(
            func.count(FileExtraction.id).label("total"),
            func.sum(
                case(
                    (FileExtraction.status == FileExtraction.STATUS_PENDING, 1),
                    else_=0,
                )
            ).label("pending"),
            func.sum(
                case(
                    (FileExtraction.status == FileExtraction.STATUS_PROCESSING, 1),
                    else_=0,
                )
            ).label("processing"),
            func.sum(
                case(
                    (FileExtraction.status == FileExtraction.STATUS_SUCCESS, 1),
                    else_=0,
                )
            ).label("success"),
            func.sum(
                case(
                    (FileExtraction.status == FileExtraction.STATUS_FAILED, 1),
                    else_=0,
                )
            ).label("failed"),
            func.sum(
                case(
                    (FileExtraction.status == FileExtraction.STATUS_SKIPPED, 1),
                    else_=0,
                )
            ).label("skipped"),
        )
        .filter(FileExtraction.run_id == run_id)
        .one()
    )

    total = totals.total or 0
    pending = totals.pending or 0
    processing = totals.processing or 0
    success = totals.success or 0
    failed = totals.failed or 0
    skipped = totals.skipped or 0

    if total == 0 and job.run_id and job.run_id != job.batch_id:
        fallback = (
            session.query(
                func.count(FileExtraction.id).label("total"),
                func.sum(
                    case(
                        (FileExtraction.status == FileExtraction.STATUS_PENDING, 1),
                        else_=0,
                    )
                ).label("pending"),
                func.sum(
                    case(
                        (FileExtraction.status == FileExtraction.STATUS_PROCESSING, 1),
                        else_=0,
                    )
                ).label("processing"),
                func.sum(
                    case(
                        (FileExtraction.status == FileExtraction.STATUS_SUCCESS, 1),
                        else_=0,
                    )
                ).label("success"),
                func.sum(
                    case(
                        (FileExtraction.status == FileExtraction.STATUS_FAILED, 1),
                        else_=0,
                    )
                ).label("failed"),
                func.sum(
                    case(
                        (FileExtraction.status == FileExtraction.STATUS_SKIPPED, 1),
                        else_=0,
                    )
                ).label("skipped"),
            )
            .filter(FileExtraction.run_id == job.batch_id)
            .one()
        )
        total = fallback.total or 0
        pending = fallback.pending or 0
        processing = fallback.processing or 0
        success = fallback.success or 0
        failed = fallback.failed or 0
        skipped = fallback.skipped or 0
        run_id = job.batch_id

    return {
        "batch_id": batch_id,
        "run_id": run_id,
        "total_files": total,
        "pending_files": pending,
        "processing_files": processing,
        "success_files": success,
        "failed_files": failed,
        "skipped_files": skipped,
    }


def get_pending_doc_ids(session: Session, batch_id: str) -> list[str]:
    job = get_batch_by_id(session, batch_id)
    if job is None:
        raise ValueError(f"Batch not found: {batch_id}")
    run_id = _resolve_run_id(job)
    rows = (
        session.query(FileExtraction.doc_id)
        .filter(
            FileExtraction.run_id == run_id,
            FileExtraction.status == FileExtraction.STATUS_PENDING,
        )
        .order_by(FileExtraction.created_at.asc())
        .all()
    )
    return [row[0] for row in rows]


def get_batch_status_summary(session: Session, batch_id: str) -> dict | None:
    result = session.execute(
        text(
            """
            SELECT
              total_files,
              files_tracked,
              files_success,
              files_failed,
              files_processing,
              files_pending,
              progress_percent,
              batch_status
            FROM batch_status_summary
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    return dict(result) if result else None


def create_or_update_run_summary(
    session: Session,
    run_id: str,
    ui_json: dict,
    summary_json: dict | None = None,
    status: str | None = None,
) -> RunSummary:
    summary = (
        session.query(RunSummary)
        .filter(RunSummary.run_id == run_id)
        .one_or_none()
    )
    if summary is None:
        summary = RunSummary(run_id=run_id, ui_json=ui_json, summary_json=summary_json or {})
        if status:
            summary.status = status
        session.add(summary)
        return summary

    summary.ui_json = ui_json
    if summary_json is not None:
        summary.summary_json = summary_json
    if status:
        summary.status = status
    summary.updated_at = func.now()
    return summary


def bulk_update_file_status(
    session: Session,
    doc_ids: Iterable[str],
    status: str,
) -> int:
    if not doc_ids:
        return 0
    return (
        session.query(FileExtraction)
        .filter(FileExtraction.doc_id.in_(list(doc_ids)))
        .update({FileExtraction.status: status}, synchronize_session=False)
    )
