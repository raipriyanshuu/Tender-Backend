"""Temporary file manager for downloading storage files to local temp."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from workers.storage.adapter import StorageAdapter


class TempFileManager:
    """Manages temporary files for parsers that require filesystem paths."""

    def __init__(self, storage: StorageAdapter):
        """
        Initialize temp file manager.
        
        Args:
            storage: Storage adapter to download files from
        """
        self.storage = storage

    @contextmanager
    def download_to_temp(self, object_key: str, suffix: str = "") -> Generator[str, None, None]:
        """
        Download file from storage to temporary local file.
        
        Context manager that:
        1. Downloads file from storage to temp location
        2. Yields temp file path for parsing
        3. Deletes temp file on exit
        
        Args:
            object_key: Storage key to download
            suffix: File suffix/extension (e.g., ".pdf", ".docx")
            
        Yields:
            Absolute path to temporary file
            
        Example:
            with temp_manager.download_to_temp("extracted/batch_123/doc.pdf", ".pdf") as temp_path:
                # Parse file at temp_path
                text = parse_pdf(temp_path)
            # Temp file is automatically deleted
        """
        temp_fd = None
        temp_path = None
        
        try:
            # Create temporary file with appropriate suffix
            temp_fd, temp_path = tempfile.mkstemp(suffix=suffix)
            
            # Download file from storage
            content = self.storage.read_file(object_key)
            
            # Write to temp file
            os.write(temp_fd, content)
            os.close(temp_fd)
            temp_fd = None  # Mark as closed
            
            # Yield path for use
            yield temp_path
            
        finally:
            # Clean up
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except Exception:
                    pass
            
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass  # Best effort cleanup

    def get_file_extension(self, object_key: str) -> str:
        """
        Extract file extension from object key.
        
        Args:
            object_key: Storage key (e.g., "extracted/batch_123/doc.pdf")
            
        Returns:
            File extension including dot (e.g., ".pdf")
        """
        return Path(object_key).suffix.lower()
