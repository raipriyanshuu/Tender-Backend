from workers.core.errors import (
    LLMError,
    ParseError,
    PermanentError,
    RateLimitError,
    RetryableError,
    TimeoutError,
    WorkerError,
    classify_error,
)


def test_error_types():
    assert WorkerError.error_type == "UNKNOWN"
    assert RetryableError.error_type == "RETRYABLE"
    assert PermanentError.error_type == "PERMANENT"
    assert TimeoutError.error_type == "TIMEOUT"
    assert RateLimitError.error_type == "RATE_LIMIT"
    assert ParseError.error_type == "PARSE_ERROR"
    assert LLMError.error_type == "LLM_ERROR"


def test_classify_error_custom():
    assert classify_error(RetryableError("x")) == "RETRYABLE"
    assert classify_error(PermanentError("x")) == "PERMANENT"
    assert classify_error(TimeoutError("x")) == "TIMEOUT"
    assert classify_error(RateLimitError("x")) == "RATE_LIMIT"
    assert classify_error(ParseError("x")) == "PARSE_ERROR"
    assert classify_error(LLMError("x")) == "LLM_ERROR"


def test_classify_error_messages():
    assert classify_error(RuntimeError("rate limit")) == "RATE_LIMIT"
    assert classify_error(RuntimeError("429 too many requests")) == "RATE_LIMIT"
    assert classify_error(RuntimeError("timed out")) == "TIMEOUT"
    assert classify_error(RuntimeError("parse failed")) == "PARSE_ERROR"
    assert classify_error(RuntimeError("openai error")) == "LLM_ERROR"
    assert classify_error(RuntimeError("permission denied")) == "PERMANENT"
    assert classify_error(RuntimeError("file not found")) == "PERMANENT"
    assert classify_error(RuntimeError("network connection error")) == "RETRYABLE"
    assert classify_error(RuntimeError("unknown")) == "UNKNOWN"
