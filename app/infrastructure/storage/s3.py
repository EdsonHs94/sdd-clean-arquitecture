"""Private S3 writes using synchronous boto3 in worker threads."""

import asyncio
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.application.errors import DependencyUnavailable


def create_s3_client(region: str, endpoint_url: str | None = None) -> Any:
    """Use the ordinary credentials provider chain with bounded network attempts."""
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint_url,
        config=Config(
            connect_timeout=3, read_timeout=5, retries={"mode": "standard", "total_max_attempts": 3}
        ),
    )


class S3FileStorage:
    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    async def upload(self, key: str, content: bytes, content_type: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError, OSError):
            raise DependencyUnavailable() from None

    async def delete(self, key: str) -> None:
        # S3 DeleteObject succeeds even when the key is already absent.
        try:
            await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError, OSError):
            raise DependencyUnavailable() from None
