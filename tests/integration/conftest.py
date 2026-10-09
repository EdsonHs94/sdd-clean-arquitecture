import asyncio
import os
from urllib.parse import urlparse
from uuid import uuid4

import boto3
import pytest
from botocore.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.persistence.session import Database
from tests.integration.helpers import migrate


@pytest.fixture
async def blank_database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail(
            "Set TEST_DATABASE_URL to a disposable PostgreSQL database for integration tests"
        )
    schema = "test_" + uuid4().hex
    admin = create_async_engine(url, hide_parameters=True)
    database = None
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        database = Database(url, connect_args={"server_settings": {"search_path": schema}})
        yield database
    finally:
        if database is not None:
            await database.engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()


@pytest.fixture
async def database(blank_database):
    await migrate(blank_database, "upgrade", "head")
    return blank_database


@pytest.fixture
async def local_s3():
    endpoint = os.environ.get("TEST_S3_ENDPOINT_URL")
    if not endpoint or urlparse(endpoint).hostname not in {"127.0.0.1", "localhost"}:
        pytest.fail("Set TEST_S3_ENDPOINT_URL to an explicitly local disposable S3 service")
    # Explicit dummy credentials guarantee the test cannot use the AWS provider chain.
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id="sdd-local",
        aws_secret_access_key="sdd-local-only-password",
        config=Config(connect_timeout=3, read_timeout=5, retries={"total_max_attempts": 1}),
    )
    bucket = "sdd-test-" + uuid4().hex
    await asyncio.to_thread(client.create_bucket, Bucket=bucket)
    try:
        yield client, bucket, endpoint
    finally:
        listing = await asyncio.to_thread(client.list_objects_v2, Bucket=bucket)
        for obj in listing.get("Contents", []):
            await asyncio.to_thread(client.delete_object, Bucket=bucket, Key=obj["Key"])
        await asyncio.to_thread(client.delete_bucket, Bucket=bucket)
        client.close()


@pytest.fixture
async def system(database, local_s3, monkeypatch):
    import app.bootstrap as bootstrap
    from app.bootstrap import create_app
    from app.infrastructure.settings import Settings
    from tests.api.helpers import client_for

    _, bucket, endpoint = local_s3
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "sdd-local")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sdd-local-only-password")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    # Retain real Database/session/repository behavior while selecting this test's schema.
    monkeypatch.setattr(bootstrap, "Database", lambda url: database)
    app = create_app(
        Settings(
            _env_file=None,
            database_url=os.environ["TEST_DATABASE_URL"],
            jwt_secret="integration-dummy-secret-at-least-32-bytes-long",
            s3_bucket=bucket,
            s3_endpoint_url=endpoint,
        )
    )
    async with client_for(app) as client:
        yield client, app, database, local_s3
