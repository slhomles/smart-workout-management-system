"""
Object Storage. DB chỉ lưu (provider, bucket, object_key), không lưu URL (design-overview §2).

- STORAGE_BACKEND=s3: ghi/đọc S3 qua boto3 (chạy trong thread, không chặn event loop).
- STORAGE_BACKEND=local: dev chưa có S3 — ghi vào LOCAL_STORAGE_DIR/<bucket>/<object_key>.
  Bản ghi media vẫn là provider 's3' + cùng bucket/key (enum DB chỉ có s3/firebase), nên khi
  chuyển sang S3 thật chỉ cần copy thư mục lên bucket.
- presign_get_url: presigned GET URL của S3 để client tải file trực tiếp (chỉ dùng khi STORAGE_BACKEND=s3).
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.models.enums import StorageProvider

settings = get_settings()


@dataclass
class StoredObject:
    provider: StorageProvider
    bucket: str
    object_key: str
    size_bytes: int
    checksum_sha256: str


def _local_path(bucket: str, object_key: str) -> Path:
    root = Path(settings.LOCAL_STORAGE_DIR).resolve()
    path = (root / bucket / object_key).resolve()
    if root not in path.parents:
        raise ValueError("object_key không hợp lệ")
    return path


def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        region_name=settings.AWS_S3_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )


async def put_object(object_key: str, data: bytes, mime_type: str) -> StoredObject:
    bucket = settings.AWS_S3_BUCKET

    def _write() -> None:
        if settings.STORAGE_BACKEND == "s3":
            _s3_client().put_object(Bucket=bucket, Key=object_key, Body=data, ContentType=mime_type)
        else:
            path = _local_path(bucket, object_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    await run_in_threadpool(_write)
    return StoredObject(
        provider=StorageProvider.S3,
        bucket=bucket,
        object_key=object_key,
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
    )


async def read_object(bucket: str, object_key: str) -> bytes | None:
    """Đọc nội dung file; None nếu không tồn tại (vd: media seed chưa có file thật)."""

    def _read() -> bytes | None:
        if settings.STORAGE_BACKEND == "s3":
            client = _s3_client()
            try:
                return client.get_object(Bucket=bucket, Key=object_key)["Body"].read()
            except client.exceptions.NoSuchKey:
                return None
        path = _local_path(bucket, object_key)
        return path.read_bytes() if path.is_file() else None

    return await run_in_threadpool(_read)


async def presign_get_url(bucket: str, object_key: str, expires_in: int) -> str:
    """Sinh presigned GET URL của S3, hết hạn sau `expires_in` giây.

    Việc ký chạy cục bộ (không gọi mạng) nhưng boto3 là thư viện đồng bộ nên vẫn chạy trong thread.
    Không bắt exception: service gọi hàm này tự chuyển lỗi thành 503.
    """

    def _presign() -> str:
        return _s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": object_key},
            ExpiresIn=expires_in,
        )

    return await run_in_threadpool(_presign)
