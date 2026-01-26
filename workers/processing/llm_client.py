from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from workers.config import Config
from workers.core.errors import LLMError, RateLimitError, RetryableError, TimeoutError
from workers.core.retry import RetryConfig, retry_with_backoff


def _build_extraction_prompt(text: str, source_filename: str = "document") -> str:
    return (
        f"Extract tender information from this document: {source_filename}\n\n"
        "CRITICAL EXTRACTION RULES:\n"
        "1. ALL text in *_de fields MUST be in German only\n"
        "2. NEVER return empty strings - use null if data is missing\n"
        "3. NEVER use placeholders like 'Unbekannt', 'Unknown', 'TBD', '...' - use null instead\n"
        "4. DEDUPLICATE within this document - combine similar/identical items\n"
        "5. Keep ALL extracted text CONCISE:\n"
        "   - risks: max 140 characters each (1 clear sentence)\n"
        "   - requirements: max 200 characters each (1-2 sentences)\n"
        "   - criteria: short phrase (max 80 chars)\n"
        "   - penalties: short phrase (max 120 chars)\n"
        "6. Include 'source_document' AND 'page_number' for EVERY item\n"
        "   - source_document: always set to current filename\n"
        "   - page_number: the page number where this information was found (integer or null if unknown)\n"
        "7. Prioritize QUALITY over quantity - extract only clear, actionable information\n"
        "8. For arrays: return TOP 5 most important items only (pre-filtered, deduplicated)\n\n"
        "Required JSON structure:\n"
        "{\n"
        '  "meta": {\n'
        '    "tender_id": "ID from document or null",\n'
        '    "tender_title": "Main tender title",\n'
        '    "organization": "Awarding organization name",\n'
        f'    "source_document": "{source_filename}",\n'
        '    "page_number": null\n'
        '  },\n'
        '  "executive_summary": {\n'
        '    "title_de": "Kurzfassung Titel (max 100 Zeichen)",\n'
        '    "organization_de": "Organisation auf Deutsch",\n'
        '    "brief_description_de": "Detaillierte Zusammenfassung der Ausschreibung (~1000 Wörter). Beschreiben Sie: 1) Hauptzweck und Umfang der Ausschreibung, 2) Wichtigste Anforderungen und Leistungen, 3) Besondere Bedingungen oder Herausforderungen, 4) Relevante technische Details, 5) Vertragliche Rahmenbedingungen. Diese Zusammenfassung sollte jedem Leser ein vollständiges Verständnis der Ausschreibung ermöglichen.",\n'
        '    "location_de": "Ort/Region",\n'
        f'    "source_document": "{source_filename}",\n'
        '    "page_number": null\n'
        '  },\n'
        '  "timeline_milestones": {\n'
        '    "submission_deadline_de": "YYYY-MM-DD (exact date or null)",\n'
        '    "project_duration_de": "z.B. \'6 Monate\' or null",\n'
        f'    "source_document": "{source_filename}",\n'
        '    "page_number": null\n'
        '  },\n'
        '  "mandatory_requirements": [\n'
        '    {"requirement_de": "Kurze Anforderung (max 200 Zeichen)", "category_de": "Kategorie", "source_document": "' + source_filename + '", "page_number": null}\n'
        '  ],\n'
        '  "risks": [\n'
        '    {"risk_de": "Klares Risiko in 1 Satz (max 140 Zeichen)", "severity": "high|medium|low", "source_document": "' + source_filename + '", "page_number": null}\n'
        '  ],\n'
        '  "evaluation_criteria": [\n'
        '    {"criterion_de": "Bewertungskriterium (max 80 Zeichen)", "weight_percent": 0, "source_document": "' + source_filename + '", "page_number": null}\n'
        '  ],\n'
        '  "economic_analysis": {\n'
        '    "potentialMargin": {"text": "Kurze Einschätzung oder null", "source_document": "' + source_filename + '", "page_number": null},\n'
        '    "orderValueEstimated": {"text": "Auftragswert Schätzung oder null", "source_document": "' + source_filename + '", "page_number": null},\n'
        '    "competitiveIntensity": {"text": "Wettbewerbsintensität oder null", "source_document": "' + source_filename + '", "page_number": null},\n'
        '    "logisticsCosts": {"text": "Logistikkosten Hinweise oder null", "source_document": "' + source_filename + '", "page_number": null},\n'
        '    "contractRisk": {"text": "Vertragsrisiko Einschätzung oder null", "source_document": "' + source_filename + '", "page_number": null},\n'
        '    "criticalSuccessFactors": [\n'
        '      {"text": "Erfolgsfaktor (max 100 Zeichen)", "source_document": "' + source_filename + '", "page_number": null}\n'
        '    ]\n'
        '  },\n'
        '  "service_types": ["Leistungsart 1", "Leistungsart 2"],\n'
        '  "certifications_required": ["Zertifizierung 1 (kurz)", "Zertifizierung 2"],\n'
        '  "safety_requirements": ["Sicherheitsanforderung 1", "Sicherheitsanforderung 2"],\n'
        '  "contract_penalties": ["Vertragsstrafe (max 120 Zeichen)", "..."],\n'
        '  "submission_requirements": ["Einreichungsanforderung", "..."],\n'
        '  "process_steps": [\n'
        '    {"step": 1, "days_de": "Tag X", "title_de": "Schritt Titel (max 60 Zeichen)", "description_de": "Kurzbeschreibung (max 150 Zeichen)", "source_document": "' + source_filename + '", "page_number": null}\n'
        '  ],\n'
        '  "missing_evidence_documents": [\n'
        '    {"document_de": "Fehlender Nachweis", "source_document": "' + source_filename + '", "page_number": null}\n'
        '  ]\n'
        "}\n\n"
        "IMPORTANT ARRAY HANDLING:\n"
        "- risks: Return TOP 5 distinct risks sorted by severity (high first)\n"
        "- mandatory_requirements: Return TOP 5 most critical requirements\n"
        "- evaluation_criteria: Return TOP 5 criteria sorted by weight_percent (highest first)\n"
        "- contract_penalties: Return TOP 5 distinct penalties\n"
        "- certifications_required: Return TOP 5 distinct certifications\n"
        "- process_steps: Return TOP 6 key timeline steps (avoid duplicates)\n"
        "- criticalSuccessFactors: Return TOP 3 success factors\n\n"
        "PAGE NUMBER TRACKING:\n"
        "- For each extracted item, try to identify the page number where it appears\n"
        "- If the document has page numbers visible in the text, extract them\n"
        "- If unsure about page number, set to null (don't guess)\n"
        "- Page numbers help users verify information in source documents\n\n"
        "Document content:\n"
        f"{text}\n\n"
        "Return ONLY valid JSON (no markdown, no explanations):"
    )


def _parse_llm_response(response: str) -> dict:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise LLMError("Invalid JSON returned by LLM")


def _map_openai_error(error: Exception) -> Exception:
    message = str(error).lower()
    if "rate limit" in message or "429" in message:
        return RateLimitError(str(error))
    if "timeout" in message or "timed out" in message:
        return TimeoutError(str(error))
    return RetryableError(str(error))


def extract_tender_data(text: str, config: Config, source_filename: str = "document") -> dict[str, Any]:
    if not config.openai_api_key or config.openai_api_key == "your_openai_api_key_here":
        raise LLMError("OPENAI_API_KEY is not configured. Please set a valid API key in workers/.env")
    
    try:
        client = OpenAI(api_key=config.openai_api_key)
    except TypeError as exc:
        # If OpenAI client initialization fails with proxy error, provide helpful message
        if 'proxies' in str(exc):
            raise LLMError(
                "OpenAI client initialization failed. Please upgrade the openai package: "
                "pip install --upgrade openai"
            ) from exc
        raise
    
    prompt = _build_extraction_prompt(text, source_filename)

    retry_config = RetryConfig(
        max_attempts=config.max_retry_attempts,
        base_delay_seconds=config.retry_base_delay_seconds,
        max_delay_seconds=config.retry_max_delay_seconds,
        retryable_exceptions=(RateLimitError, TimeoutError, RetryableError, LLMError),
    )

    @retry_with_backoff(retry_config)
    def _call_llm() -> str:
        model_candidates = [
            "gpt-5.2",
            "gpt-5.1",
            "gpt-4o",
        ]
        # Allow override while still keeping fallback order
        if config.openai_model and config.openai_model not in model_candidates:
            model_candidates.insert(0, config.openai_model)

        last_error: Exception | None = None
        for model in model_candidates:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_completion_tokens=config.openai_max_tokens,
                    temperature=0,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:  # noqa: BLE001 - keep retry behavior simple
                last_error = exc
                continue

        raise _map_openai_error(last_error or Exception("LLM request failed"))

    raw = _call_llm()
    return _parse_llm_response(raw)



