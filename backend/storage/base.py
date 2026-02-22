from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from pathlib import Path
from dataclasses import dataclass


@dataclass
class StorageConfig:
    backend: str  # 'local' or 's3'
    base_path: Optional[str] = None  # For local storage
    bucket_name: Optional[str] = None  # For S3
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = None
    endpoint_url: Optional[str] = None  # For S3-compatible services like MinIO


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def upload_file(self, local_path: str, object_key: str) -> str:
        """Upload a file to storage. Returns the object URI."""
        pass

    @abstractmethod
    def download_file(self, object_key: str, local_path: str) -> None:
        """Download a file from storage to local path."""
        pass

    @abstractmethod
    def upload_folder(self, local_folder: str, prefix: str) -> List[str]:
        """Upload all files in a folder. Returns list of object keys."""
        pass

    @abstractmethod
    def list_prefix(self, prefix: str) -> List[str]:
        """List all object keys under a prefix."""
        pass

    @abstractmethod
    def get_signed_url(self, object_key: str, expires_in: int = 3600) -> str:
        """Get a signed URL for temporary access. Expires in seconds."""
        pass

    @abstractmethod
    def delete_object(self, object_key: str) -> None:
        """Delete an object from storage."""
        pass
