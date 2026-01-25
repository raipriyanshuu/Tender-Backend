from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from workers.config import Config
from workers.database import operations
from workers.database.models import FileExtraction, RunSummary


def _normalize_text(text: str) -> str:
    """Normalize text for deduplication (lowercase, strip, collapse whitespace)"""
    import re
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)  # Collapse multiple spaces
    return text


def _is_placeholder(text: Any) -> bool:
    """Check if text is a placeholder/empty value"""
    if not text:
        return True
    if isinstance(text, str):
        normalized = text.lower().strip()
        placeholders = ['unbekannt', 'unknown', 'tbd', 'n/a', 'nicht vorhanden', 
                       'keine angabe', 'unspecified', '...', 'null', 'none']
        return normalized in placeholders or len(normalized) < 3
    return False


def _deduplicate_risks(risks: list[dict]) -> list[dict]:
    """Deduplicate and filter risks, keeping highest severity for duplicates"""
    if not risks:
        return []
    
    # Filter empty/placeholder risks
    valid_risks = [r for r in risks if r.get('risk_de') and not _is_placeholder(r.get('risk_de'))]
    
    # Deduplicate by normalized risk_de, keep highest severity
    severity_order = {'high': 3, 'medium': 2, 'low': 1}
    seen = {}
    for risk in valid_risks:
        normalized = _normalize_text(risk.get('risk_de', ''))
        if not normalized:
            continue
        existing = seen.get(normalized)
        risk_severity = severity_order.get(risk.get('severity', 'low').lower(), 1)
        if not existing or risk_severity > severity_order.get(existing.get('severity', 'low').lower(), 1):
            seen[normalized] = risk
    
    # Sort by severity, then by original text
    result = sorted(seen.values(), 
                   key=lambda x: (-severity_order.get(x.get('severity', 'low').lower(), 1), x.get('risk_de', '')))
    return result[:5]  # Top 5


def _deduplicate_requirements(reqs: list[dict]) -> list[dict]:
    """Deduplicate and filter requirements"""
    if not reqs:
        return []
    
    valid_reqs = [r for r in reqs if r.get('requirement_de') and not _is_placeholder(r.get('requirement_de'))]
    
    seen = {}
    for req in valid_reqs:
        normalized = _normalize_text(req.get('requirement_de', ''))
        if not normalized:
            continue
        if normalized not in seen:
            seen[normalized] = req
    
    return list(seen.values())[:5]  # Top 5


def _deduplicate_criteria(criteria: list[dict]) -> list[dict]:
    """Deduplicate evaluation criteria, sum weights for duplicates"""
    if not criteria:
        return []
    
    valid_criteria = [c for c in criteria if c.get('criterion_de') and not _is_placeholder(c.get('criterion_de'))]
    
    seen = {}
    for criterion in valid_criteria:
        normalized = _normalize_text(criterion.get('criterion_de', ''))
        if not normalized:
            continue
        weight = criterion.get('weight_percent', 0)
        if normalized in seen:
            # Sum weights for duplicates
            seen[normalized]['weight_percent'] = seen[normalized].get('weight_percent', 0) + weight
        else:
            seen[normalized] = criterion.copy()
    
    # Sort by weight descending
    result = sorted(seen.values(), key=lambda x: -x.get('weight_percent', 0))
    return result[:5]  # Top 5


def _deduplicate_process_steps(steps: list[dict]) -> list[dict]:
    """Deduplicate process steps by normalized title"""
    if not steps:
        return []
    
    valid_steps = [s for s in steps if s.get('title_de') and not _is_placeholder(s.get('title_de'))]
    
    seen = {}
    for step in valid_steps:
        normalized = _normalize_text(step.get('title_de', ''))
        if not normalized:
            continue
        if normalized not in seen:
            seen[normalized] = step
    
    # Sort by step number if available
    result = sorted(seen.values(), key=lambda x: x.get('step', 999))
    return result[:6]  # Top 6


def _deduplicate_simple_array(items: list, max_count: int = 5) -> list:
    """Deduplicate simple string arrays"""
    if not items:
        return []
    
    # Filter placeholders
    valid = [item for item in items if item and not _is_placeholder(str(item))]
    
    # Deduplicate by normalized text
    seen = {}
    for item in valid:
        normalized = _normalize_text(str(item))
        if normalized and normalized not in seen:
            seen[normalized] = item
    
    return list(seen.values())[:max_count]


def _merge_dicts(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge extracted JSON chunks with smart deduplication"""
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

    # Apply smart deduplication to specific arrays
    if 'risks' in merged and isinstance(merged['risks'], list):
        merged['risks'] = _deduplicate_risks(merged['risks'])
    
    if 'mandatory_requirements' in merged and isinstance(merged['mandatory_requirements'], list):
        merged['mandatory_requirements'] = _deduplicate_requirements(merged['mandatory_requirements'])
    
    if 'evaluation_criteria' in merged and isinstance(merged['evaluation_criteria'], list):
        merged['evaluation_criteria'] = _deduplicate_criteria(merged['evaluation_criteria'])
    
    if 'process_steps' in merged and isinstance(merged['process_steps'], list):
        merged['process_steps'] = _deduplicate_process_steps(merged['process_steps'])
    
    if 'contract_penalties' in merged and isinstance(merged['contract_penalties'], list):
        merged['contract_penalties'] = _deduplicate_simple_array(merged['contract_penalties'], 5)
    
    if 'certifications_required' in merged and isinstance(merged['certifications_required'], list):
        merged['certifications_required'] = _deduplicate_simple_array(merged['certifications_required'], 5)
    
    if 'service_types' in merged and isinstance(merged['service_types'], list):
        merged['service_types'] = _deduplicate_simple_array(merged['service_types'], 5)

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
