from datetime import datetime, timedelta, timezone

from workers.core.idempotency import should_reprocess_file
from workers.database.models import FileExtraction


def _make_file(status: str) -> FileExtraction:
    file_extraction = FileExtraction(
        run_id="run-1",
        doc_id="doc-1",
        filename="file.pdf",
        extracted_json={},
        status=status,
    )
    return file_extraction


def test_should_reprocess_success():
    file_extraction = _make_file(FileExtraction.STATUS_SUCCESS)
    assert should_reprocess_file(file_extraction, max_retry_attempts=3) is False


def test_should_reprocess_permanent_failure():
    file_extraction = _make_file(FileExtraction.STATUS_FAILED)
    file_extraction.error_type = FileExtraction.ERROR_PERMANENT
    assert should_reprocess_file(file_extraction, max_retry_attempts=3) is False


def test_should_reprocess_retryable_failure():
    file_extraction = _make_file(FileExtraction.STATUS_FAILED)
    file_extraction.error_type = FileExtraction.ERROR_RETRYABLE
    file_extraction.retry_count = 1
    assert should_reprocess_file(file_extraction, max_retry_attempts=3) is True


def test_should_reprocess_pending_without_start_time():
    file_extraction = _make_file(FileExtraction.STATUS_PENDING)
    file_extraction.processing_started_at = None
    assert should_reprocess_file(file_extraction, max_retry_attempts=3) is True


def test_should_reprocess_stale_processing():
    file_extraction = _make_file(FileExtraction.STATUS_PROCESSING)
    file_extraction.processing_started_at = datetime.now(timezone.utc) - timedelta(hours=2)
    assert should_reprocess_file(file_extraction, max_retry_attempts=3, stale_seconds=60) is True


def test_should_not_reprocess_recent_processing():
    file_extraction = _make_file(FileExtraction.STATUS_PROCESSING)
    file_extraction.processing_started_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    assert should_reprocess_file(file_extraction, max_retry_attempts=3, stale_seconds=60) is False
