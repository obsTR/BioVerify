from .base import StorageBackend, StorageConfig
from .local import LocalStorageBackend
from .s3 import S3StorageBackend


def create_storage_backend(config: StorageConfig) -> StorageBackend:
    """Factory function to create the appropriate storage backend."""
    if config.backend == 'local':
        return LocalStorageBackend(config)
    elif config.backend == 's3':
        return S3StorageBackend(config)
    else:
        raise ValueError(f"Unknown storage backend: {config.backend}")
