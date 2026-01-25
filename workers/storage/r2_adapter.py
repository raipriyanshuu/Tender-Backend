"""Cloudflare R2 storage adapter using S3-compatible API."""

from __future__ import annotations

from typing import List

from workers.core.errors import PermanentError, RetryableError
from workers.storage.adapter import StorageAdapter

# boto3 is optional - only required when using R2
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    _BOTO3_AVAILABLE = True
except ImportError:
    _BOTO3_AVAILABLE = False


class R2StorageAdapter(StorageAdapter):
    """Storage adapter for Cloudflare R2 (S3-compatible)."""

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        environment: str = "prod",
        region: str = "auto",
    ):
        """
        Initialize R2 storage adapter.
        
        Args:
            account_id: Cloudflare account ID
            access_key_id: R2 access key ID
            secret_access_key: R2 secret access key
            bucket_name: R2 bucket name
            environment: Environment prefix (e.g., "prod", "dev", "staging")
            region: R2 region (default: "auto")
        """
        if not _BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required for R2 storage. Install with: pip install boto3"
            )

        self.bucket_name = bucket_name
        self.environment = environment
        
        # Construct R2 endpoint URL
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        
        # Initialize S3 client with R2 endpoint
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

    def _add_environment_prefix(self, object_key: str) -> str:
        """Add environment prefix to object key."""
        # Remove leading slashes
        clean_key = object_key.lstrip("/")
        return f"{self.environment}/{clean_key}"

    def _remove_environment_prefix(self, full_key: str) -> str:
        """Remove environment prefix from object key."""
        prefix = f"{self.environment}/"
        if full_key.startswith(prefix):
            return full_key[len(prefix):]
        return full_key

    def read_file(self, object_key: str) -> bytes:
        """Read file from R2."""
        full_key = self._add_environment_prefix(object_key)
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=full_key)
            return response["Body"].read()
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                raise PermanentError(f"File not found in R2: {object_key}") from exc
            elif error_code in ("AccessDenied", "InvalidAccessKeyId"):
                raise PermanentError(f"Permission denied for R2: {object_key}") from exc
            else:
                raise RetryableError(f"Failed to read from R2: {object_key}") from exc
        except NoCredentialsError as exc:
            raise PermanentError("R2 credentials not configured") from exc
        except Exception as exc:
            raise RetryableError(f"Failed to read from R2: {object_key}") from exc

    def write_file(self, object_key: str, content: bytes) -> None:
        """Write file to R2."""
        full_key = self._add_environment_prefix(object_key)
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=full_key,
                Body=content,
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("AccessDenied", "InvalidAccessKeyId"):
                raise PermanentError(f"Permission denied for R2: {object_key}") from exc
            else:
                raise RetryableError(f"Failed to write to R2: {object_key}") from exc
        except NoCredentialsError as exc:
            raise PermanentError("R2 credentials not configured") from exc
        except Exception as exc:
            raise RetryableError(f"Failed to write to R2: {object_key}") from exc

    def file_exists(self, object_key: str) -> bool:
        """Check if file exists in R2."""
        full_key = self._add_environment_prefix(object_key)
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=full_key)
            return True
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                return False
            # Other errors are treated as "unknown"
            return False
        except Exception:
            return False

    def get_file_size(self, object_key: str) -> int:
        """Get file size from R2."""
        full_key = self._add_environment_prefix(object_key)
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=full_key)
            return response["ContentLength"]
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                raise PermanentError(f"File not found in R2: {object_key}") from exc
            else:
                raise RetryableError(f"Failed to get file size from R2: {object_key}") from exc
        except Exception as exc:
            raise RetryableError(f"Failed to get file size from R2: {object_key}") from exc

    def list_files(self, prefix: str) -> List[str]:
        """List files with given prefix in R2."""
        full_prefix = self._add_environment_prefix(prefix)
        try:
            files = []
            paginator = self.s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=full_prefix):
                for obj in page.get("Contents", []):
                    # Remove environment prefix from returned keys
                    key = self._remove_environment_prefix(obj["Key"])
                    files.append(key)
            return files
        except Exception as exc:
            raise RetryableError(f"Failed to list files in R2: {prefix}") from exc

    def delete_file(self, object_key: str) -> None:
        """Delete file from R2."""
        full_key = self._add_environment_prefix(object_key)
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=full_key)
        except Exception as exc:
            raise RetryableError(f"Failed to delete file from R2: {object_key}") from exc
