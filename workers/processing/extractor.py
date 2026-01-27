from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from workers.config import Config
from workers.core.errors import classify_error
from workers.core.logging import log_context, setup_logger
from workers.database import operations
from workers.processing.chunking import chunk_text
from workers.processing.llm_client import extract_tender_data, extract_critical_fields
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


def _merge_with_priority(semantic_data: dict[str, Any], critical_data: dict[str, Any]) -> dict[str, Any]:
    """
    Merge semantic extraction with critical field extraction.
    Critical fields take absolute priority over semantic fields.
    
    Args:
        semantic_data: Full extraction from Stage 2 (semantic prompt)
        critical_data: Critical fields from Stage 1 (strict prompt)
    
    Returns:
        Merged dict with critical fields overriding semantic fields
    """
    # Start with semantic data as base
    result = semantic_data.copy()
    
    # Override with critical fields (even if null - null from Stage 1 means "definitely not found")
    if critical_data.get("meta"):
        if "meta" not in result:
            result["meta"] = {}
        
        # Override tender_title if present in critical_data
        if "tender_title" in critical_data["meta"]:
            result["meta"]["tender_title"] = critical_data["meta"]["tender_title"]
        
        # Override organization if present in critical_data
        if "organization" in critical_data["meta"]:
            result["meta"]["organization"] = critical_data["meta"]["organization"]
    
    if critical_data.get("timeline_milestones"):
        if "timeline_milestones" not in result:
            result["timeline_milestones"] = {}
        
        # Override submission_deadline_de if present in critical_data
        if "submission_deadline_de" in critical_data["timeline_milestones"]:
            result["timeline_milestones"]["submission_deadline_de"] = critical_data["timeline_milestones"]["submission_deadline_de"]
    
    return result



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
            
            # ============================================================
            # TWO-STAGE EXTRACTION PIPELINE
            # ============================================================
            
            # STAGE 1: Extract critical fields with STRICT legal logic
            # Fields: tender_title, organization, submission_deadline_de
            logger.info(f"[Stage 1] Extracting critical fields with strict logic from {len(chunks_for_llm)} chunks...")
            critical_results = [
                extract_critical_fields(chunk, config, source_filename)
                for chunk in chunks_for_llm
            ]
            critical_merged = merge_extractions(critical_results)
            logger.info(f"[Stage 1] Critical fields extracted: {critical_merged.get('meta', {}).keys()}")
            
            # STAGE 2: Extract remaining fields with SEMANTIC logic
            # All other fields (risks, requirements, etc.)
            logger.info(f"[Stage 2] Extracting remaining fields with semantic logic from {len(chunks_for_llm)} chunks...")
            semantic_results = [
                extract_tender_data(chunk, config, source_filename)
                for chunk in chunks_for_llm
            ]
            semantic_merged = merge_extractions(semantic_results)
            logger.info(f"[Stage 2] Semantic fields extracted")
            
            # STAGE 3: Merge with priority to critical fields
            logger.info("[Stage 3] Merging results (critical fields take priority)...")
            final_extraction = _merge_with_priority(semantic_merged, critical_merged)
            logger.info("[Stage 3] Merge complete")

            operations.mark_file_success(session, doc_id, final_extraction)
            logger.info(f"Successfully processed {doc_id}")
        except Exception as exc:  # noqa: BLE001 - centralize error handling
            logger.error(f"Failed to process {doc_id}: {exc}")
            error_type = classify_error(exc)
            operations.mark_file_failed(session, doc_id, str(exc), error_type)
            # Don't re-raise - let the endpoint return success after committing the failure
            # The orchestrator will see the FAILED status and count it appropriately
