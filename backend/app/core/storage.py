import logging
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseStorageProvider(ABC):
    """Abstract interface for file object storage (Local filesystem, S3, MinIO, R2)."""

    @abstractmethod
    async def upload_file(
        self,
        file_bytes: bytes,
        file_key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Store file bytes under unique key and return storage path / reference."""
        pass

    @abstractmethod
    async def download_file(self, file_key: str) -> bytes:
        """Retrieve stored file bytes by key."""
        pass

    @abstractmethod
    async def delete_file(self, file_key: str) -> bool:
        """Delete file by key from storage."""
        pass

    @abstractmethod
    async def get_download_url(self, file_key: str, expires_in: int = 3600) -> str:
        """Generate download URL or presigned temporary URL."""
        pass


class LocalStorageProvider(BaseStorageProvider):
    """Local filesystem storage adapter for local execution, Docker volumes, and tests."""

    def __init__(self, base_path: str | None = None) -> None:
        self.base_path = Path(base_path or settings.LOCAL_STORAGE_PATH).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, file_key: str) -> Path:
        # Prevent path traversal attacks
        safe_key = file_key.lstrip("/\\")
        target = (self.base_path / safe_key).resolve()
        if not str(target).startswith(str(self.base_path)):
            raise ValueError(f"Illegal path traversal attempt: {file_key}")
        return target

    async def upload_file(
        self,
        file_bytes: bytes,
        file_key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        path = self._resolve_safe_path(file_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_bytes)
        return str(path)

    async def download_file(self, file_key: str) -> bytes:
        path = self._resolve_safe_path(file_key)
        if not path.is_file():
            raise FileNotFoundError(f"File key '{file_key}' does not exist.")
        return path.read_bytes()

    async def delete_file(self, file_key: str) -> bool:
        try:
            path = self._resolve_safe_path(file_key)
            if path.is_file():
                path.unlink()
                return True
        except Exception as e:
            logger.warning(f"Error deleting local file {file_key}: {e}")
        return False

    async def get_download_url(self, file_key: str, expires_in: int = 3600) -> str:
        # For local execution, route to the backend download streaming endpoint
        return f"/api/v1/documents/download-file?key={file_key}"


class S3StorageProvider(BaseStorageProvider):
    """S3-compatible object storage provider (AWS S3, MinIO, Cloudflare R2)."""

    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        session = boto3.session.Session()
        client_kwargs = {
            "service_name": "s3",
            "region_name": settings.STORAGE_REGION,
            "aws_access_key_id": settings.STORAGE_ACCESS_KEY,
            "aws_secret_access_key": settings.STORAGE_SECRET_KEY,
            "config": Config(signature_version="s3v4"),
        }
        if settings.STORAGE_ENDPOINT:
            client_kwargs["endpoint_url"] = settings.STORAGE_ENDPOINT

        self.s3_client = session.client(**client_kwargs)
        self.bucket = settings.STORAGE_BUCKET

    async def upload_file(
        self,
        file_bytes: bytes,
        file_key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=file_key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return f"s3://{self.bucket}/{file_key}"

    async def download_file(self, file_key: str) -> bytes:
        resp = self.s3_client.get_object(Bucket=self.bucket, Key=file_key)
        return resp["Body"].read()

    async def delete_file(self, file_key: str) -> bool:
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=file_key)
            return True
        except Exception as e:
            logger.warning(f"Failed deleting S3 object {file_key}: {e}")
            return False

    async def get_download_url(self, file_key: str, expires_in: int = 3600) -> str:
        return self.s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": file_key},
            ExpiresIn=expires_in,
        )


def get_storage_provider() -> BaseStorageProvider:
    """Return configured storage provider with automatic local fallback."""
    provider_type = (settings.STORAGE_PROVIDER or "local").lower()

    if provider_type == "s3":
        if settings.STORAGE_ACCESS_KEY and settings.STORAGE_SECRET_KEY:
            try:
                return S3StorageProvider()
            except Exception as e:
                logger.error(
                    f"Failed to initialize S3 storage provider: {e}. Falling back to local."
                )
        else:
            logger.warning("S3 credentials missing in environment. Falling back to local storage.")

    return LocalStorageProvider()
