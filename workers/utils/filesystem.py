from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from workers.core.errors import PermanentError, RetryableError


def resolve_storage_path(relative_path: str, base_path: str = "/shared") -> str:
    clean_relative = relative_path.lstrip("/\\")
    return str(Path(base_path) / clean_relative)


def ensure_directory_exists(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def get_file_type(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    mapping = {
        ".pdf": "pdf",
        ".doc": "word",
        ".docx": "word",
        ".xls": "excel",
        ".xlsx": "excel",
        ".zip": "zip",
        ".txt": "text",
        ".csv": "csv",
        # GAEB formats (German tender exchange format)
        ".x83": "gaeb",
        ".x84": "gaeb",
        ".x85": "gaeb",
        ".x86": "gaeb",
        ".x89": "gaeb",
        ".d83": "gaeb",
        ".d84": "gaeb",
        ".d85": "gaeb",
        ".d86": "gaeb",
        ".d89": "gaeb",
        ".p83": "gaeb",
        ".p84": "gaeb",
        ".p85": "gaeb",
        ".p86": "gaeb",
        ".p89": "gaeb",
        ".gaeb": "gaeb",
    }
    return mapping.get(ext, "unknown")


def safe_read_file(file_path: str) -> bytes:
    try:
        with open(file_path, "rb") as handle:
            return handle.read()
    except FileNotFoundError as exc:
        raise PermanentError(f"File not found: {file_path}") from exc
    except PermissionError as exc:
        raise PermanentError(f"Permission denied: {file_path}") from exc
    except Exception as exc:  # noqa: BLE001 - keep retry behavior simple
        raise RetryableError(f"Failed to read file: {file_path}") from exc


def safe_write_file(file_path: str, content: bytes) -> None:
    try:
        ensure_directory_exists(str(Path(file_path).parent))
        with open(file_path, "wb") as handle:
            handle.write(content)
    except PermissionError as exc:
        raise PermanentError(f"Permission denied: {file_path}") from exc
    except Exception as exc:  # noqa: BLE001 - keep retry behavior simple
        raise RetryableError(f"Failed to write file: {file_path}") from exc


def get_file_size(file_path: str) -> int:
    try:
        return os.path.getsize(file_path)
    except FileNotFoundError as exc:
        raise PermanentError(f"File not found: {file_path}") from exc
    except Exception as exc:  # noqa: BLE001 - keep retry behavior simple
        raise RetryableError(f"Failed to get file size: {file_path}") from exc


def list_files_in_directory(directory_path: str, pattern: str = "*") -> list[str]:
    directory = Path(directory_path)
    if not directory.exists():
        raise PermanentError(f"Directory not found: {directory_path}")
    return [str(path) for path in directory.glob(pattern) if path.is_file()]
