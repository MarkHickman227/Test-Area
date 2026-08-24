from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from app.config import Settings


class StorageBackend:
    def put(self, key: str, data: bytes, content_type: str) -> None:
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def presign(self, key: str, ttl_seconds: int) -> str:
        raise NotImplementedError


class LocalStorage(StorageBackend):
    def __init__(self, root: str, public_prefix: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_prefix = public_prefix.rstrip("/")

    def _path(self, key: str) -> Path:
        safe = key.lstrip("/")
        path = (self.root / safe).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("Invalid storage key")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._path(key).write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def presign(self, key: str, ttl_seconds: int) -> str:
        # Application-proxied downloads are the default for local storage.
        return f"{self.public_prefix}/v1/library/files/{quote(key, safe='')}"


class MinioStorage(StorageBackend):
    def __init__(self, settings: Settings) -> None:
        from minio import Minio

        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        from io import BytesIO

        self.client.put_object(
            self.bucket,
            key,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def get(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete(self, key: str) -> None:
        self.client.remove_object(self.bucket, key)

    def exists(self, key: str) -> bool:
        from minio.error import S3Error

        try:
            self.client.stat_object(self.bucket, key)
            return True
        except S3Error:
            return False

    def presign(self, key: str, ttl_seconds: int) -> str:
        from datetime import timedelta

        return self.client.presigned_get_object(
            self.bucket, key, expires=timedelta(seconds=ttl_seconds)
        )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_object_key(user_id: str, job_id: str, kind: str, ext: str = "png") -> str:
    return f"users/{user_id}/jobs/{job_id}/{kind}-{uuid4().hex}.{ext}"
