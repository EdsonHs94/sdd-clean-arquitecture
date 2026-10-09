import threading
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError

from app.application.errors import DependencyUnavailable
from app.infrastructure.storage.s3 import S3FileStorage, create_s3_client


async def test_exact_private_upload_and_worker_thread():
    client = Mock()
    main_thread = threading.get_ident()
    threads = []
    client.put_object.side_effect = lambda **kwargs: threads.append(threading.get_ident())
    await S3FileStorage(client, "private-bucket").upload(
        "files/opaque-id", b"binary\x00payload", "application/custom"
    )
    client.put_object.assert_called_once_with(
        Bucket="private-bucket",
        Key="files/opaque-id",
        Body=b"binary\x00payload",
        ContentType="application/custom",
    )
    assert threads[0] != main_thread


async def test_exact_delete_and_idempotent_absent_response():
    client = Mock()
    client.delete_object.return_value = {}
    storage = S3FileStorage(client, "private-bucket")
    await storage.delete("files/missing")
    await storage.delete("files/missing")
    assert client.delete_object.call_count == 2
    client.delete_object.assert_called_with(Bucket="private-bucket", Key="files/missing")


@pytest.mark.parametrize("operation", ["upload", "delete"])
@pytest.mark.parametrize("failure", ["client", "connect_timeout", "read_timeout", "os"])
async def test_expected_sdk_failures_are_sanitized(operation, failure):
    errors = {
        "client": ClientError({"Error": {"Code": "AccessDenied", "Message": "private key"}}, "S3"),
        "connect_timeout": ConnectTimeoutError(endpoint_url="http://private-endpoint"),
        "read_timeout": ReadTimeoutError(endpoint_url="http://private-endpoint"),
        "os": OSError("private credentials"),
    }
    client = Mock()
    getattr(
        client, "put_object" if operation == "upload" else "delete_object"
    ).side_effect = errors[failure]
    storage = S3FileStorage(client, "private-bucket")
    with pytest.raises(DependencyUnavailable) as raised:
        if operation == "upload":
            await storage.upload("files/opaque-id", b"secret", "text/plain")
        else:
            await storage.delete("files/opaque-id")
    assert str(raised.value) == "Service unavailable"
    assert raised.value.__suppress_context__


def test_client_configuration_is_bounded_and_uses_provider_chain():
    with patch("app.infrastructure.storage.s3.boto3.client") as factory:
        create_s3_client("us-east-1", "http://127.0.0.1:59000")
    kwargs = factory.call_args.kwargs
    assert factory.call_args.args == ("s3",)
    assert kwargs["region_name"] == "us-east-1"
    assert kwargs["endpoint_url"] == "http://127.0.0.1:59000"
    assert kwargs["config"].connect_timeout == 3
    assert kwargs["config"].read_timeout == 5
    assert kwargs["config"].retries == {"mode": "standard", "total_max_attempts": 3}
    assert "aws_access_key_id" not in kwargs
    assert "aws_secret_access_key" not in kwargs
