import asyncio
from uuid import uuid4

import httpx
import pytest
from botocore.exceptions import ClientError

from app.infrastructure.storage.s3 import S3FileStorage

pytestmark = pytest.mark.integration


async def test_private_byte_roundtrip_content_type_and_idempotent_delete(local_s3):
    client, bucket, endpoint = local_s3
    key = "files/" + str(uuid4())
    storage = S3FileStorage(client, bucket)
    await storage.upload(key, b"binary\x00content", "application/custom")
    result = await asyncio.to_thread(client.get_object, Bucket=bucket, Key=key)
    try:
        assert await asyncio.to_thread(result["Body"].read) == b"binary\x00content"
        assert result["ContentType"] == "application/custom"
    finally:
        result["Body"].close()
    async with httpx.AsyncClient() as anonymous:
        response = await anonymous.get(f"{endpoint}/{bucket}/{key}")
        assert response.status_code == 403
    await storage.delete(key)
    await storage.delete(key)
    with pytest.raises(ClientError) as raised:
        await asyncio.to_thread(client.get_object, Bucket=bucket, Key=key)
    assert raised.value.response["Error"]["Code"] == "NoSuchKey"
