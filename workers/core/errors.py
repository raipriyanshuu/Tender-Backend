from __future__ import annotations


class WorkerError(Exception):
    error_type = "UNKNOWN"


class RetryableError(WorkerError):
    error_type = "RETRYABLE"


class PermanentError(WorkerError):
    error_type = "PERMANENT"


class TimeoutError(WorkerError):
    error_type = "TIMEOUT"


class RateLimitError(WorkerError):
    error_type = "RATE_LIMIT"


class ParseError(WorkerError):
    error_type = "PARSE_ERROR"


class LLMError(WorkerError):
    error_type = "LLM_ERROR"


def classify_error(error: Exception) -> str:
    if hasattr(error, "error_type"):
        return getattr(error, "error_type")

    message = str(error).lower()

    if "rate limit" in message or "429" in message:
        return "RATE_LIMIT"

    if "timeout" in message or "timed out" in message:
        return "TIMEOUT"

    if "parse" in message or "decode" in message:
        return "PARSE_ERROR"

    if "openai" in message or "llm" in message:
        return "LLM_ERROR"

    if "permission" in message or "not found" in message:
        return "PERMANENT"

    if "connection" in message or "network" in message:
        return "RETRYABLE"

    return "UNKNOWN"
