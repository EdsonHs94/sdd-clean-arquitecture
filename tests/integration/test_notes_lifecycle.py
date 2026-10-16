import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from tests.integration.test_lifecycle import account

pytestmark = pytest.mark.integration


async def test_real_notes_lifecycle_isolation_and_concurrent_patch(system, monkeypatch):
    client, app, _, _ = system
    _, owner_headers = await account(client)
    _, other_headers = await account(client, "bob@example.com")

    async def forbidden_storage(*args, **kwargs):
        raise AssertionError("Notes must not invoke file storage")

    monkeypatch.setattr(app.state.file_storage, "upload", forbidden_storage)
    monkeypatch.setattr(app.state.file_storage, "delete", forbidden_storage)
    created = await client.post(
        "/notes", json={"title": "  Shopping  ", "body": " bread\n "}, headers=owner_headers
    )
    assert created.status_code == 201
    note = created.json()
    assert set(note) == {"id", "title", "body", "created_at", "updated_at"}
    assert note["title"] == "Shopping" and note["body"] == " bread\n "
    assert note["created_at"] == note["updated_at"]
    path = f"/notes/{note['id']}"
    assert (await client.get(path, headers=owner_headers)).json() == note
    assert (await client.get("/notes", headers=owner_headers)).json() == [note]
    assert (await client.get("/notes", headers=other_headers)).json() == []
    for method in ("GET", "PATCH", "DELETE"):
        denied = await client.request(method, path, headers=other_headers, json={"body": "stolen"})
        missing = await client.request(
            method, f"/notes/{uuid4()}", headers=other_headers, json={"body": "stolen"}
        )
        assert denied.status_code == missing.status_code == 404
        assert denied.json() == missing.json() == {"detail": "Note not found"}

    responses = await asyncio.gather(
        client.patch(path, json={"title": "New title"}, headers=owner_headers),
        client.patch(path, json={"body": ""}, headers=owner_headers),
    )
    assert [response.status_code for response in responses] == [200, 200]
    updated = (await client.get(path, headers=owner_headers)).json()
    assert updated["title"] == "New title" and updated["body"] == ""
    assert updated["created_at"] == note["created_at"]
    rejected = await client.patch(
        path, json={"title": "must not persist", "body": None}, headers=owner_headers
    )
    assert rejected.status_code == 422
    assert (await client.get(path, headers=owner_headers)).json() == updated
    deleted = await client.delete(path, headers=owner_headers)
    assert deleted.status_code == 204 and deleted.content == b""
    assert (await client.get("/notes", headers=owner_headers)).json() == []
    assert (await client.delete(path, headers=owner_headers)).status_code == 404
    assert (
        await client.patch(path, json={"body": "gone"}, headers=owner_headers)
    ).status_code == 404


@pytest.mark.parametrize("operation", ["create", "patch", "delete"])
async def test_real_note_commit_failures_rollback_before_http_success(
    system, monkeypatch, operation
):
    client, app, _, _ = system
    _, headers = await account(client)
    created = await client.post(
        "/notes", json={"title": "Original", "body": "text"}, headers=headers
    )
    assert created.status_code == 201
    original = created.json()
    path = f"/notes/{original['id']}"
    factory = app.state.note_repository_factory

    def failing_factory(session):
        async def failed_commit():
            await session.flush()
            raise OperationalError("commit", {}, RuntimeError("private database details"))

        session.commit = failed_commit
        return factory(session)

    monkeypatch.setattr(app.state, "note_repository_factory", failing_factory)
    if operation == "create":
        response = await client.post(
            "/notes", json={"title": "Uncommitted", "body": "text"}, headers=headers
        )
    elif operation == "patch":
        response = await client.patch(path, json={"title": "Uncommitted"}, headers=headers)
    else:
        response = await client.delete(path, headers=headers)
    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}
    monkeypatch.setattr(app.state, "note_repository_factory", factory)
    assert (await client.get(path, headers=headers)).json() == original
    assert (await client.get("/notes", headers=headers)).json() == [original]
