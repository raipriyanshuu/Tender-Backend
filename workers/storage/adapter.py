"""Abstract storage adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class StorageAdapter(ABC):
    """Abstract interface for storage operations."""

    @abstractmethod
    def read_file(self, object_key: str) -> bytes:
        """
        Read file contents from storage.
        
        Args:
            object_key: Storage key (e.g., "extracted/batch_123/doc.pdf")
            
        Returns:
            File contents as bytes
            
        Raises:
            PermanentError: If file not found or permission denied
            RetryableError: If temporary network/storage error
        """
        pass

    @abstractmethod
    def write_file(self, object_key: str, content: bytes) -> None:
        """
        Write file contents to storage.
        
        Args:
            object_key: Storage key (e.g., "uploads/batch_123.zip")
            content: File contents as bytes
            
        Raises:
            PermanentError: If permission denied
            RetryableError: If temporary network/storage error
        """
        pass

    @abstractmethod
    def file_exists(self, object_key: str) -> bool:
        """
        Check if file exists in storage.
        
        Args:
            object_key: Storage key
            
        Returns:
            True if file exists, False otherwise
        """
        pass

    @abstractmethod
    def get_file_size(self, object_key: str) -> int:
        """
        Get file size in bytes.
        
        Args:
            object_key: Storage key
            
        Returns:
            File size in bytes
            
        Raises:
            PermanentError: If file not found
            RetryableError: If temporary error
        """
        pass

    @abstractmethod
    def list_files(self, prefix: str) -> List[str]:
        """
        List files with given prefix.
        
        Args:
            prefix: Key prefix (e.g., "extracted/batch_123/")
            
        Returns:
            List of object keys
        """
        pass

    @abstractmethod
    def delete_file(self, object_key: str) -> None:
        """
        Delete file from storage.
        
        Args:
            object_key: Storage key
            
        Raises:
            RetryableError: If temporary error
        """
        pass
