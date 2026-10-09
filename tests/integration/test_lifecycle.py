import asyncio
from unittest.mock import Mock
from uuid import UUID

import pytest
from botocore.exceptions import ClientError
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.infrastructure.persistence.file_repository import SqlAlchemyFileRepository
from app.infrastructure.persistence.models import UserModel
from app.infrastructure.persistence.user_repository import SqlAlchemyUserRepository

pytestmark = pytest.mark.integration


async def account(client, email="alice@example.com"):
    response = await client.post(
        "/users",
        json={
            "name": " Alice ",
            "email": email,
            "password": "integration-password",
        },
    )
    assert response.status_code == 201
    profile = response.json()
    login = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "integration-password",
        },
    )
    assert login.status_code == 200
    assert login.json()["expires_in"] == 3600
    return profile, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def files_for(database, owner):
    async with database.session() as session:
        return await SqlAlchemyFileRepository(session).list_by_owner(UUID(owner))


def fail_commit_factory(session):
    async def failing_commit():
        await session.flush()
        raise OperationalError("commit", {}, RuntimeError("private database details"))

    session.commit = failing_commit
    return SqlAlchemyFileRepository(session)


async def object_keys(local_s3):
    client, bucket, _ = local_s3
    listing = await asyncio.to_thread(client.list_objects_v2, Bucket=bucket)
    return [entry["Key"] for entry in listing.get("Contents", [])]


async def test_real_adapters_lifecycle_and_second_user_denial(system):
    client, app, database, s3 = system
    profile, headers = await account(client)
    second, other_headers = await account(client, "bob@example.com")
    assert (await client.get("/me", headers=headers)).json() == profile
    assert (await client.get("/me", headers=other_headers)).json() == second
    async with database.session() as session:
        stored = await SqlAlchemyUserRepository(session).get_by_id(UUID(profile["id"]))
        assert stored.password_hash.startswith("$argon2id$")
        assert await app.state.password_hasher.verify("integration-password", stored.password_hash)
    assert (await client.get("/files", headers=other_headers)).json() == []
    responses = [
        await client.post("/files", headers=headers, files={"file": ("same.bin", payload)})
        for payload in (b"first", b"second")
    ]
    assert all(response.status_code == 201 for response in responses)
    ids = [response.json()["id"] for response in responses]
    assert ids[0] != ids[1]
    rows = await files_for(database, profile["id"])
    assert len(rows) == 2
    s3_client, bucket, _ = s3
    for row, content in zip(rows, (b"first", b"second"), strict=True):
        obj = await asyncio.to_thread(s3_client.get_object, Bucket=bucket, Key=row.storage_key)
        try:
            assert await asyncio.to_thread(obj["Body"].read) == content
        finally:
            obj["Body"].close()
        assert row.storage_key not in responses[0].text
    listing = await client.get("/files", headers=headers)
    assert [file["id"] for file in listing.json()] == ids
    assert (await client.get(f"/files/{ids[0]}", headers=headers)).json() == responses[0].json()
    for method in (client.get, client.delete):
        denied = await method(f"/files/{ids[0]}", headers=other_headers)
        assert denied.status_code == 404
        assert denied.json() == {"detail": "File not found"}
    assert len(await object_keys(s3)) == 2
    assert len(await files_for(database, profile["id"])) == 2
    assert (
        await client.get("/files", headers={"Authorization": "Bearer tampered"})
    ).status_code == 401
    removed = await client.delete(f"/files/{ids[0]}", headers=headers)
    assert removed.status_code == 204 and removed.content == b""
    assert (await client.delete(f"/files/{ids[0]}", headers=headers)).status_code == 404
    assert len(await object_keys(s3)) == 1
    assert len(await files_for(database, profile["id"])) == 1
    assert database.engine.sync_engine.pool.checkedout() == 0


async def test_real_database_duplicate_registration_race(system):
    client, _, database, _ = system
    responses = await asyncio.gather(
        *(
            client.post(
                "/users",
                json={
                    "name": "Alice",
                    "email": email,
                    "password": "integration-password",
                },
            )
            for email in (" Alice@Example.com ", "alice@example.com")
        )
    )
    assert sorted(response.status_code for response in responses) == [201, 409]
    async with database.session() as session:
        assert await session.scalar(select(func.count()).select_from(UserModel)) == 1


@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_upload_persistence_failure_compensates_or_records_orphan(
    system, monkeypatch, caplog, cleanup_fails
):
    client, app, database, s3 = system
    profile, headers = await account(client)
    monkeypatch.setattr(app.state, "file_repository_factory", fail_commit_factory)
    if cleanup_fails:
        monkeypatch.setattr(
            app.state.file_storage._client,
            "delete_object",
            Mock(
                side_effect=ClientError({"Error": {"Code": "AccessDenied"}}, "DeleteObject"),
            ),
        )
    response = await client.post(
        "/files", headers=headers, files={"file": ("private-name", b"abc")}
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}
    assert await files_for(database, profile["id"]) == []
    keys = await object_keys(s3)
    assert len(keys) == int(cleanup_fails)
    if cleanup_fails:
        assert "cleanup failed" in caplog.text.lower()
        assert keys[0] not in caplog.text
        assert "private-name" not in caplog.text
        assert "private database details" not in caplog.text


async def test_real_deletion_retry_after_metadata_commit_failure(system, monkeypatch):
    client, app, database, s3 = system
    profile, headers = await account(client)
    uploaded = await client.post("/files", headers=headers, files={"file": ("a", b"abc")})
    file_id = uploaded.json()["id"]
    original_factory = app.state.file_repository_factory
    monkeypatch.setattr(app.state, "file_repository_factory", fail_commit_factory)
    failed = await client.delete(f"/files/{file_id}", headers=headers)
    assert failed.status_code == 503
    assert len(await files_for(database, profile["id"])) == 1
    assert await object_keys(s3) == []
    monkeypatch.setattr(app.state, "file_repository_factory", original_factory)
    retry = await client.delete(f"/files/{file_id}", headers=headers)
    assert retry.status_code == 204
    assert await files_for(database, profile["id"]) == []


async def test_real_storage_failure_creates_no_metadata(system, monkeypatch):
    client, app, database, s3 = system
    profile, headers = await account(client)
    monkeypatch.setattr(
        app.state.file_storage._client,
        "put_object",
        Mock(
            side_effect=ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject"),
        ),
    )
    response = await client.post("/files", headers=headers, files={"file": ("a", b"abc")})
    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}
    assert await files_for(database, profile["id"]) == []
    assert await object_keys(s3) == []
