import boto3
from botocore.exceptions import ClientError
from typing import List
from pathlib import Path
from .base import StorageBackend, StorageConfig


class S3StorageBackend(StorageBackend):
    """S3-compatible storage backend for production."""

    def __init__(self, config: StorageConfig):
        if not config.bucket_name:
            raise ValueError("bucket_name is required for S3 storage")

        self.bucket_name = config.bucket_name
        self.client = boto3.client(
            's3',
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            region_name=config.aws_region,
            endpoint_url=config.endpoint_url,
        )

    def ensure_bucket_exists(self) -> None:
        """Create the bucket if it does not exist (e.g. MinIO on first run)."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            return
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code not in ('404', 'NoSuchBucket'):
                raise RuntimeError(f"Cannot access bucket {self.bucket_name}: {e}") from e

        try:
            self.client.create_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code in ('BucketAlreadyOwnedByYou', 'BucketAlreadyExists'):
                return
            raise RuntimeError(f"Failed to create bucket {self.bucket_name}: {e}") from e

    def upload_file(self, local_path: str, object_key: str) -> str:
        """Upload a file to S3."""
        try:
            self.client.upload_file(local_path, self.bucket_name, object_key)
            return f"s3://{self.bucket_name}/{object_key}"
        except ClientError as e:
            raise RuntimeError(f"Failed to upload file: {e}")

    def download_file(self, object_key: str, local_path: str) -> None:
        """Download a file from S3."""
        try:
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            self.client.download_file(self.bucket_name, object_key, local_path)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise FileNotFoundError(f"Object not found: {object_key}")
            raise RuntimeError(f"Failed to download file: {e}")

    def upload_folder(self, local_folder: str, prefix: str) -> List[str]:
        """Upload all files in a folder to S3."""
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
        """List all object keys under a prefix."""
        try:
            paginator = self.client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            keys = []
            for page in pages:
                if 'Contents' in page:
                    keys.extend([obj['Key'] for obj in page['Contents']])
            return keys
        except ClientError as e:
            raise RuntimeError(f"Failed to list objects: {e}")

    def get_signed_url(self, object_key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for temporary access."""
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_key},
                ExpiresIn=expires_in,
            )
            # Replace internal Docker hostnames with localhost for browser access
            # This handles cases where endpoint_url is http://minio:9000 (internal)
            # but browsers need http://localhost:9000
            if '://minio:' in url:
                url = url.replace('://minio:', '://localhost:')
            return url
        except ClientError as e:
            raise RuntimeError(f"Failed to generate signed URL: {e}")

    def delete_object(self, object_key: str) -> None:
        """Delete an object from S3."""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_key)
        except ClientError as e:
            raise RuntimeError(f"Failed to delete object: {e}")
