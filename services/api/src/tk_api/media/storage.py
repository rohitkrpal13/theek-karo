"""Object storage adapters for media (API.md §7).

Three modes (ADR-027-style: keep tests hermetic, exercise real infra live):

- ``memory``: bytes in a dict. Used by unit tests. Direct PUT/POST via the API
  route in dev mode; no presigned URLs.
- ``local``: files under ``TK_MEDIA_LOCAL_DIR``. Dev default; uploads/downloads
  flow through the API itself.
- ``minio``: full presigned PUT/GET against MinIO/S3 (production-shaped flow).

The upload client flow is identical regardless of mode: the upload request
returns either a presigned PUT URL (minio) or null (the client then PUTs to the
API's dev upload route). Downloads always return a URL through
``download_url`` (presigned for minio, an API route otherwise).
"""

from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Protocol

from minio import Minio
from minio.error import S3Error

from tk_api.core.config import Settings


class StorageAdapter(Protocol):
    def request_upload(self, key: str, size: int) -> str | None: ...

    def download_url(self, bucket: str, key: str, expires_seconds: int = 900) -> str: ...

    def stat(self, bucket: str, key: str) -> int: ...

    def read_prefix(self, bucket: str, key: str, length: int) -> bytes: ...

    def save_bytes(self, bucket: str, key: str, data: bytes) -> None: ...


class MemoryStorageAdapter:
    """In-memory byte store for unit tests; no URLs (API routes handle I/O)."""

    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], bytes] = {}

    def request_upload(self, key: str, size: int) -> str | None:
        return None

    def download_url(self, bucket: str, key: str, expires_seconds: int = 900) -> str:
        return f"/api/v1/media/object/{bucket}/{key}"

    def stat(self, bucket: str, key: str) -> int:
        data = self._objects.get((bucket, key))
        if data is None:
            raise FileNotFoundError(key)
        return len(data)

    def read_prefix(self, bucket: str, key: str, length: int) -> bytes:
        data = self._objects.get((bucket, key))
        if data is None:
            raise FileNotFoundError(key)
        return data[:length]

    def save_bytes(self, bucket: str, key: str, data: bytes) -> None:
        self._objects[(bucket, key)] = data


class LocalStorageAdapter:
    """Files on disk; API routes read/write the bytes directly."""

    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, bucket: str, key: str) -> Path:
        # keys are generated server-side ("media/2026/08/<uuid>") — safe join
        target = (self._base / bucket / key).resolve()
        if not target.is_relative_to(self._base.resolve()):
            raise ValueError("key escapes storage root")
        return target

    def request_upload(self, key: str, size: int) -> str | None:
        return None

    def download_url(self, bucket: str, key: str, expires_seconds: int = 900) -> str:
        return f"/api/v1/media/object/{bucket}/{key}"

    def stat(self, bucket: str, key: str) -> int:
        return self._path(bucket, key).stat().st_size

    def read_prefix(self, bucket: str, key: str, length: int) -> bytes:
        with self._path(bucket, key).open("rb") as fh:
            return fh.read(length)

    def save_bytes(self, bucket: str, key: str, data: bytes) -> None:
        path = self._path(bucket, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


class MinioStorageAdapter:
    """MinIO/S3 with presigned URLs (production-shaped).

    Presigned URLs must be signed against the *public* endpoint reachable by the
    client (host browser), because SigV4 canonicalizes the Host header; a second
    client bound to the internal endpoint (``media_minio_endpoint``) handles
    object operations from the API side.
    """

    def __init__(self, settings: Settings) -> None:
        self._client = Minio(
            settings.media_minio_endpoint,
            access_key=settings.media_minio_access_key,
            secret_key=settings.media_minio_secret_key,
            secure=settings.media_minio_secure,
            region=settings.media_minio_region,
        )
        self._signer = Minio(
            settings.media_minio_public_endpoint,
            access_key=settings.media_minio_access_key,
            secret_key=settings.media_minio_secret_key,
            secure=settings.media_minio_secure,
            # region pinned so presigning never performs a network bucket-lookup
            # against the public endpoint (unreachable from inside compose);
            # must match the bucket region for SigV4 (S3 production path)
            region=settings.media_minio_region,
        )
        self._bucket = settings.media_minio_bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
        except S3Error:
            # during compose startup the bucket may exist already
            pass

    def request_upload(self, key: str, size: int) -> str | None:
        return self._signer.presigned_put_object(self._bucket, key, expires=timedelta(seconds=900))

    def download_url(self, bucket: str, key: str, expires_seconds: int = 900) -> str:
        return self._signer.presigned_get_object(
            self._bucket, key, expires=timedelta(seconds=expires_seconds)
        )

    def stat(self, bucket: str, key: str) -> int:
        size = self._client.stat_object(self._bucket, key).size
        return size if size is not None else 0

    def read_prefix(self, bucket: str, key: str, length: int) -> bytes:
        response = self._client.get_object(self._bucket, key, length=length)
        try:
            return response.read(length)
        finally:
            response.close()
            response.release_conn()

    def save_bytes(self, bucket: str, key: str, data: bytes) -> None:
        self._client.put_object(
            self._bucket,
            key,
            BytesIO(data),
            length=len(data),
            content_type="application/octet-stream",
        )


def build_storage(settings: Settings) -> StorageAdapter:
    mode = settings.media_storage_mode
    if mode == "memory":
        return MemoryStorageAdapter()
    if mode == "minio":
        return MinioStorageAdapter(settings)
    return LocalStorageAdapter(Path(settings.media_local_dir))
