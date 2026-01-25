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
        f"Extract tender information from the following document: {source_filename}\n\n"
        "Return ONLY valid JSON with ALL fields below. Include 'source_document' for EVERY field.\n\n"
        "Required JSON structure:\n"
        "{\n"
        '  "meta": {\n'
        '    "tender_id": "...",\n'
        '    "tender_title": "...",\n'
        '    "organization": "...",\n'
        f'    "source_document": "{source_filename}"\n'
        '  },\n'
        '  "executive_summary": {\n'
        '    "title_de": "...",\n'
        '    "organization_de": "...",\n'
        '    "brief_description_de": "...",\n'
        '    "location_de": "...",\n'
        f'    "source_document": "{source_filename}"\n'
        '  },\n'
        '  "timeline_milestones": {\n'
        '    "submission_deadline_de": "YYYY-MM-DD",\n'
        '    "project_duration_de": "...",\n'
        f'    "source_document": "{source_filename}"\n'
        '  },\n'
        '  "mandatory_requirements": [\n'
        '    {"requirement_de": "...", "category_de": "...", "source_document": "' + source_filename + '"}\n'
        '  ],\n'
        '  "risks": [\n'
        '    {"risk_de": "...", "severity": "high/medium/low", "source_document": "' + source_filename + '"}\n'
        '  ],\n'
        '  "evaluation_criteria": [\n'
        '    {"criterion_de": "...", "weight_percent": 0, "source_document": "' + source_filename + '"}\n'
        '  ],\n'
        '  "economic_analysis": {\n'
        '    "potentialMargin": {"text": "...", "source_document": "' + source_filename + '"},\n'
        '    "orderValueEstimated": {"text": "...", "source_document": "' + source_filename + '"},\n'
        '    "competitiveIntensity": {"text": "...", "source_document": "' + source_filename + '"},\n'
        '    "logisticsCosts": {"text": "...", "source_document": "' + source_filename + '"},\n'
        '    "contractRisk": {"text": "...", "source_document": "' + source_filename + '"},\n'
        '    "criticalSuccessFactors": [\n'
        '      {"text": "...", "source_document": "' + source_filename + '"}\n'
        '    ]\n'
        '  },\n'
        '  "service_types": ["..."],\n'
        '  "certifications_required": ["..."],\n'
        '  "safety_requirements": ["..."],\n'
        '  "contract_penalties": ["..."],\n'
        '  "submission_requirements": ["..."],\n'
        '  "process_steps": [\n'
        '    {"step": 1, "days_de": "...", "title_de": "...", "description_de": "...", "source_document": "' + source_filename + '"}\n'
        '  ],\n'
        '  "missing_evidence_documents": [\n'
        '    {"document_de": "...", "source_document": "' + source_filename + '"}\n'
        '  ]\n'
        "}\n\n"
        "Document content:\n"
        f"{text}\n\n"
        "Return valid JSON only:"
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
        try:
            response = client.chat.completions.create(
                model=config.openai_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=config.openai_max_tokens,
                temperature=0,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001 - keep retry behavior simple
            raise _map_openai_error(exc) from exc

    raw = _call_llm()
    return _parse_llm_response(raw)



