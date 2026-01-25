from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    batch_id = Column(Text, unique=True, nullable=False)
    zip_path = Column(Text, nullable=False)
    run_id = Column(Text)
    total_files = Column(Integer, nullable=False, server_default="0")
    uploaded_by = Column(Text)
    status = Column(Text, nullable=False, server_default="pending")
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    STATUS_PENDING = "pending"
    STATUS_QUEUED = "queued"
    STATUS_EXTRACTING = "extracting"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_COMPLETED_WITH_ERRORS = "completed_with_errors"
    STATUS_FAILED = "failed"


class FileExtraction(Base):
    __tablename__ = "file_extractions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    run_id = Column(Text, nullable=False)
    source = Column(Text, nullable=False, server_default="gdrive")
    doc_id = Column(Text, nullable=False, unique=True)
    filename = Column(Text, nullable=False)
    file_type = Column(Text)
    extracted_json = Column(JSONB, nullable=False, server_default="{}")
    status = Column(Text, nullable=False, server_default="pending")
    error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Added in migration 002
    file_path = Column(Text)
    processing_started_at = Column(DateTime(timezone=True))
    processing_completed_at = Column(DateTime(timezone=True))
    processing_duration_ms = Column(Integer)
    retry_count = Column(Integer, server_default="0")
    error_type = Column(Text)

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_SKIPPED = "SKIPPED"

    ERROR_RETRYABLE = "RETRYABLE"
    ERROR_PERMANENT = "PERMANENT"
    ERROR_TIMEOUT = "TIMEOUT"
    ERROR_RATE_LIMIT = "RATE_LIMIT"
    ERROR_PARSE_ERROR = "PARSE_ERROR"
    ERROR_LLM_ERROR = "LLM_ERROR"
    ERROR_UNKNOWN = "UNKNOWN"
    ERROR_UNKNOWN = "UNKNOWN"


class RunSummary(Base):
    __tablename__ = "run_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    run_id = Column(Text, nullable=False, unique=True)
    summary_json = Column(JSONB, nullable=False, server_default="{}")
    ui_json = Column(JSONB, nullable=False, server_default="{}")
    total_files = Column(Integer, server_default="0")
    success_files = Column(Integer, server_default="0")
    failed_files = Column(Integer, server_default="0")
    status = Column(Text, nullable=False, server_default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
