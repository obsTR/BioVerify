import os
import shutil
from pathlib import Path
from typing import List
from .base import StorageBackend, StorageConfig


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend for development."""

    def __init__(self, config: StorageConfig):
        if not config.base_path:
            raise ValueError("base_path is required for local storage")
        self.base_path = Path(config.base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_full_path(self, object_key: str) -> Path:
        """Convert object key to local filesystem path."""
        # Normalize path to prevent directory traversal
        parts = object_key.split('/')
        safe_parts = [p for p in parts if p and p != '..']
        return self.base_path / Path(*safe_parts)

    def upload_file(self, local_path: str, object_key: str) -> str:
        """Upload a file to local storage."""
        target_path = self._get_full_path(object_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, target_path)
        return f"file://{target_path}"

    def download_file(self, object_key: str, local_path: str) -> None:
        """Download a file from local storage."""
        source_path = self._get_full_path(object_key)
        if not source_path.exists():
            raise FileNotFoundError(f"Object not found: {object_key}")
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, local_path)

    def upload_folder(self, local_folder: str, prefix: str) -> List[str]:
        """Upload all files in a folder."""
        local_path = Path(local_folder)
        if not local_path.is_dir():
            raise ValueError(f"Not a directory: {local_folder}")

        uploaded_keys = []
        for file_path in local_path.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_path)
                object_key = f"{prefix}/{relative_path}".replace('\\', '/')
                self.upload_file(str(file_path), object_key)
                uploaded_keys.append(object_key)

        return uploaded_keys

    def list_prefix(self, prefix: str) -> List[str]:
        """List all files under a prefix."""
        prefix_path = self._get_full_path(prefix)
        if not prefix_path.exists():
            return []

        keys = []
        if prefix_path.is_file():
            return [prefix]
        elif prefix_path.is_dir():
            for file_path in prefix_path.rglob('*'):
                if file_path.is_file():
                    relative = file_path.relative_to(self.base_path)
                    keys.append(str(relative).replace('\\', '/'))
        return keys

    def get_signed_url(self, object_key: str, expires_in: int = 3600) -> str:
        """For local storage, return an API URL that serves the file."""
        full_path = self._get_full_path(object_key)
        if not full_path.exists():
            raise FileNotFoundError(f"Object not found: {object_key}")
        # Return a relative API path - the API will serve it
        # URL-encode the object_key to handle special characters
        import urllib.parse
        encoded_key = urllib.parse.quote(object_key, safe='/')
        # Use absolute URL with localhost (browser needs full URL, not relative)
        # In production, this should use the actual API host
        api_host = os.getenv("API_BASE_URL", "http://localhost:8000")
        return f"{api_host}/api/storage/{encoded_key}"

    def delete_object(self, object_key: str) -> None:
        """Delete an object from local storage."""
        target_path = self._get_full_path(object_key)
        if target_path.exists():
            if target_path.is_file():
                target_path.unlink()
            elif target_path.is_dir():
                shutil.rmtree(target_path)
