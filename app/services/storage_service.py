from functools import lru_cache

import boto3
from botocore.config import Config

from app.core.config import settings


@lru_cache
def _get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=(
            f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        ),
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


class StorageService:

    @staticmethod
    def download_object(object_key: str) -> bytes:
        client = _get_r2_client()
        response = client.get_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=object_key,
        )
        return response["Body"].read()
