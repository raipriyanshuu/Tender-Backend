"""Local filesystem storage adapter."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from workers.core.errors import PermanentError, RetryableError
from workers.storage.adapter import StorageAdapter


class LocalStorageAdapter(StorageAdapter):
    """Storage adapter for local filesystem."""

    def __init__(self, base_path: str):
        """
        Initialize local storage adapter.
        
        Args:
            base_path: Base directory for storage (e.g., "/shared")
        """
        self.base_path = Path(base_path)
        if not self.base_path.exists():
            raise ValueError(f"Base path does not exist: {base_path}")

    def _resolve_path(self, object_key: str) -> Path:
        """Convert object key to absolute filesystem path."""
        # Remove leading slashes
        clean_key = object_key.lstrip("/\\")
        return self.base_path / clean_key

    def read_file(self, object_key: str) -> bytes:
        """Read file from local filesystem."""
        file_path = self._resolve_path(object_key)
        try:
            with open(file_path, "rb") as handle:
                return handle.read()
        except FileNotFoundError as exc:
            raise PermanentError(f"File not found: {object_key}") from exc
        except PermissionError as exc:
            raise PermanentError(f"Permission denied: {object_key}") from exc
        except Exception as exc:
            raise RetryableError(f"Failed to read file: {object_key}") from exc

    def write_file(self, object_key: str, content: bytes) -> None:
        """Write file to local filesystem."""
        file_path = self._resolve_path(object_key)
        try:
            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "wb") as handle:
                handle.write(content)
        except PermissionError as exc:
            raise PermanentError(f"Permission denied: {object_key}") from exc
        except Exception as exc:
            raise RetryableError(f"Failed to write file: {object_key}") from exc

    def file_exists(self, object_key: str) -> bool:
        """Check if file exists on local filesystem."""
        file_path = self._resolve_path(object_key)
        return file_path.exists() and file_path.is_file()

    def get_file_size(self, object_key: str) -> int:
        """Get file size from local filesystem."""
        file_path = self._resolve_path(object_key)
        try:
            return os.path.getsize(file_path)
        except FileNotFoundError as exc:
            raise PermanentError(f"File not found: {object_key}") from exc
        except Exception as exc:
            raise RetryableError(f"Failed to get file size: {object_key}") from exc

    def list_files(self, prefix: str) -> List[str]:
        """List files with given prefix on local filesystem."""
        prefix_path = self._resolve_path(prefix)
        if not prefix_path.exists():
            return []
        
        files = []
        if prefix_path.is_file():
            # Prefix is a file
            files.append(prefix)
        elif prefix_path.is_dir():
            # Prefix is a directory - list all files recursively
            for path in prefix_path.rglob("*"):
                if path.is_file():
                    # Convert back to relative key
                    relative = path.relative_to(self.base_path)
                    files.append(str(relative).replace("\\", "/"))
        
        return files

    def delete_file(self, object_key: str) -> None:
        """Delete file from local filesystem."""
        file_path = self._resolve_path(object_key)
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as exc:
            raise RetryableError(f"Failed to delete file: {object_key}") from exc
