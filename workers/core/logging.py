from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from typing import Iterator

from workers.config import Config


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "time": self.formatTime(record, self.datefmt),
        }

        if hasattr(record, "batch_id"):
            payload["batch_id"] = record.batch_id
        if hasattr(record, "doc_id"):
            payload["doc_id"] = record.doc_id

        return json.dumps(payload, ensure_ascii=True)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        parts = [record.levelname, record.name, record.getMessage()]
        if hasattr(record, "batch_id"):
            parts.append(f"batch_id={record.batch_id}")
        if hasattr(record, "doc_id"):
            parts.append(f"doc_id={record.doc_id}")
        return " | ".join(parts)


def setup_logger(name: str, config: Config) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(config.log_level)
    logger.propagate = False

    if logger.handlers:
        return logger

    console_handler = logging.StreamHandler()
    formatter: logging.Formatter
    if config.log_format == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        config.log_file_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
    )
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    return logger


@contextmanager
def log_context(logger: logging.Logger, **context) -> Iterator[logging.Logger]:
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        for key, value in context.items():
            setattr(record, key, value)
        return record

    logging.setLogRecordFactory(record_factory)
    try:
        yield logger
    finally:
        logging.setLogRecordFactory(old_factory)
