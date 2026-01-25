"""Storage abstraction layer for file operations."""

from workers.storage.adapter import StorageAdapter
from workers.storage.local_adapter import LocalStorageAdapter
from workers.storage.r2_adapter import R2StorageAdapter

__all__ = ["StorageAdapter", "LocalStorageAdapter", "R2StorageAdapter"]
