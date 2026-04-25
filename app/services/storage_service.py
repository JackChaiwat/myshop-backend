"""storage_service.py — Cloudflare R2 via aioboto3 (async, non-blocking)"""
import uuid
import aioboto3
from fastapi import UploadFile
from app.core.config import settings

# FIX: Use aioboto3 instead of sync boto3 — prevents blocking the event loop
_session = aioboto3.Session()


def _client():
    return _session.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


async def upload_image(file: UploadFile, folder: str = "images") -> str:
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin"
    key = f"{folder}/{uuid.uuid4()}.{ext}"
    content = await file.read()
    async with _client() as s3:
        await s3.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=key,
            Body=content,
            ContentType=file.content_type or "application/octet-stream",
        )
    return f"{settings.R2_PUBLIC_URL}/{key}"


async def delete_image(url: str):
    key = url.replace(f"{settings.R2_PUBLIC_URL}/", "")
    async with _client() as s3:
        await s3.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
