from workers.core.retry import RetryConfig, retry_with_backoff


def test_retry_success_after_failures(monkeypatch):
    calls = {"count": 0}

    def target():
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("temporary")
        return "ok"

    monkeypatch.setattr("workers.core.retry.time.sleep", lambda _x: None)

    config = RetryConfig(max_attempts=3, base_delay_seconds=0.01, max_delay_seconds=0.05)
    wrapped = retry_with_backoff(config)(target)

    assert wrapped() == "ok"
    assert calls["count"] == 3


def test_retry_stops_after_max_attempts(monkeypatch):
    calls = {"count": 0}

    def target():
        calls["count"] += 1
        raise RuntimeError("always failing")

    monkeypatch.setattr("workers.core.retry.time.sleep", lambda _x: None)

    config = RetryConfig(max_attempts=1, base_delay_seconds=0.01, max_delay_seconds=0.05)
    wrapped = retry_with_backoff(config)(target)

    try:
        wrapped()
        assert False, "Expected RuntimeError"
    except RuntimeError:
        pass

    assert calls["count"] == 2
