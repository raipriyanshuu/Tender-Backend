from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 3
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 60.0
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)


def calculate_backoff(attempt: int, base_delay: float, max_delay: float) -> float:
    delay = base_delay * (2 ** attempt)
    jitter = random.uniform(0, base_delay * (2 ** max(attempt - 1, 0)))
    return min(delay + jitter, max_delay)


def should_retry(error: Exception, attempt: int, config: RetryConfig) -> bool:
    if attempt >= config.max_attempts:
        return False
    return isinstance(error, config.retryable_exceptions)


def retry_with_backoff(
    config: RetryConfig,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as error:  # noqa: BLE001 - explicit retry behavior
                    if not should_retry(error, attempt, config):
                        raise
                    delay = calculate_backoff(
                        attempt=attempt,
                        base_delay=config.base_delay_seconds,
                        max_delay=config.max_delay_seconds,
                    )
                    time.sleep(delay)
                    attempt += 1

        return wrapper

    return decorator


def run_with_backoff(
    func: Callable[..., T],
    config: RetryConfig,
    *args,
    **kwargs,
) -> T:
    return retry_with_backoff(config)(func)(*args, **kwargs)
