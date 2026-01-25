from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from workers.config import Config
from workers.core.errors import classify_error
from workers.core.logging import log_context, setup_logger
from workers.database import operations
from workers.processing.chunking import chunk_text
from workers.processing.llm_client import extract_tender_data
from workers.processing.embeddings import select_relevant_chunks
from workers.processing.parsers import parse_file
from workers.utils.filesystem import resolve_storage_path


def merge_extractions(chunks_data: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for chunk in chunks_data:
        for key, value in chunk.items():
            if key not in merged:
                merged[key] = value
                continue
            if isinstance(value, list) and isinstance(merged[key], list):
                merged[key] = merged[key] + [item for item in value if item not in merged[key]]
            elif isinstance(value, dict) and isinstance(merged[key], dict):
                for nested_key, nested_value in value.items():
                    if merged[key].get(nested_key) in (None, "", []):
                        merged[key][nested_key] = nested_value
            else:
                if merged[key] in (None, "", []):
                    merged[key] = value
    return merged


def process_file(session: Session, doc_id: str, config: Config) -> None:
    logger = setup_logger("worker.extractor", config)

    with log_context(logger, doc_id=doc_id):
        file_extraction = operations.get_file_by_doc_id(session, doc_id)
        if file_extraction is None:
            raise ValueError(f"File not found: {doc_id}")

        operations.mark_file_processing_start(session, doc_id)
        session.flush()

        try:
            if not file_extraction.file_path:
                raise ValueError(f"file_path is missing for doc_id={doc_id}")

            # Create storage adapter
            storage = config.create_storage_adapter()
            
            # Import temp file manager
            from workers.storage.temp_file_manager import TempFileManager
            temp_manager = TempFileManager(storage)
            
            object_key = file_extraction.file_path
            logger.info(f"Processing file from storage: {object_key} (type: {file_extraction.file_type})")
            
            # Get file extension for temp file
            file_extension = temp_manager.get_file_extension(object_key)
            
            # Download to temp file and parse
            with temp_manager.download_to_temp(object_key, suffix=file_extension) as temp_path:
                logger.info(f"Downloaded to temp file: {temp_path}")
                
                # Parse file with OCR support for scanned PDFs
                raw_text = parse_file(
                    file_path=object_key,  # For type detection
                    temp_file_path=temp_path,  # Actual file to parse
                    enable_ocr=config.enable_ocr,
                    ocr_max_pages=config.ocr_max_pages
                )
                logger.info(f"Parsed {len(raw_text)} characters from {object_key}")
            
            # Temp file is automatically deleted after context manager exits
            
            chunks = chunk_text(raw_text, max_chunk_size=3000, overlap=200)
            if not chunks:
                raise ValueError("No text extracted from file")
            
            logger.info(f"Split into {len(chunks)} chunks, calling LLM...")
            # Pass filename to LLM for source tracking
            source_filename = file_extraction.filename or "document"
            retrieval_query = (
                "Extract risks, mandatory requirements, timelines, economic factors, "
                "penalties, and evaluation criteria"
            )
            selected_chunks = select_relevant_chunks(
                chunks=chunks,
                query=retrieval_query,
                config=config,
                logger=logger,
                doc_id=doc_id,
                source_filename=source_filename,
            )
            chunks_for_llm = selected_chunks or chunks
            chunk_results = [
                extract_tender_data(chunk, config, source_filename)
                for chunk in chunks_for_llm
            ]
            final_extraction = merge_extractions(chunk_results)

            operations.mark_file_success(session, doc_id, final_extraction)
            logger.info(f"Successfully processed {doc_id}")
        except Exception as exc:  # noqa: BLE001 - centralize error handling
            logger.error(f"Failed to process {doc_id}: {exc}")
            error_type = classify_error(exc)
            operations.mark_file_failed(session, doc_id, str(exc), error_type)
            # Don't re-raise - let the endpoint return success after committing the failure
            # The orchestrator will see the FAILED status and count it appropriately
