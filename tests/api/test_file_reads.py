from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.errors import DependencyUnavailable
from app.domain.entities import User
from tests.unit.application.fakes import make_file


async def test_two_user_listing_isolation_order_and_empty(
    api, api_context, file_context, file_auth
):
    repo, storage = file_context
    owner, headers = file_auth
    other = User(
        uuid4(), "Bob", "bob@example.com", "private-hash", datetime(2026, 1, 1, tzinfo=UTC)
    )
    await api_context[1].add(other)
    token = await api_context[3].issue(other.id)
    foreign = make_file(other.id, 4)
    first, second = make_file(owner.id, 1), make_file(owner.id, 2)
    early = make_file(owner.id, 3, datetime(2025, 1, 1, tzinfo=UTC))
    empty = await api.get("/files", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == []
    for file in (second, foreign, first, early):
        await repo.add(file)
    response = await api.get(f"/files?user_id={other.id}", headers=headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        str(early.id),
        str(first.id),
        str(second.id),
    ]
    response = await api.get("/files", headers={"Authorization": f"Bearer {token.access_token}"})
    assert [item["id"] for item in response.json()] == [str(foreign.id)]
    assert storage.calls == []


async def test_owned_metadata_allowlist_no_private_fields_or_storage_access(
    api, file_context, file_auth
):
    repo, storage = file_context
    owner, headers = file_auth
    file = make_file(owner.id)
    await repo.add(file)
    response = await api.get(f"/files/{file.id}", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "id": str(file.id),
        "filename": file.original_name,
        "content_type": file.content_type,
        "size_bytes": file.size,
        "created_at": "2026-01-01T00:00:00Z",
    }
    listing = await api.get("/files", headers=headers)
    assert listing.json() == [response.json()]
    for result in (response, listing):
        assert file.storage_key not in result.text
        assert str(owner.id) not in result.text
    assert storage.calls == []


async def test_foreign_and_missing_responses_are_identical(api, file_context, file_auth):
    repo, storage = file_context
    file = make_file(uuid4())
    await repo.add(file)
    responses = [
        await api.get(f"/files/{file_id}?user_id={file.user_id}", headers=file_auth[1])
        for file_id in (file.id, uuid4())
    ]
    assert all(response.status_code == 404 for response in responses)
    assert responses[0].json() == responses[1].json() == {"detail": "File not found"}
    assert storage.calls == []


async def test_malformed_uuid_validated_only_after_authentication(api, file_context, file_auth):
    repo, storage = file_context
    repo.get_owned = AsyncMock(wraps=repo.get_owned)
    authenticated = await api.get("/files/not-a-uuid", headers=file_auth[1])
    assert authenticated.status_code == 422
    (detail,) = authenticated.json()["detail"]
    assert detail["loc"] == ["path", "file_id"]
    assert set(detail) == {"loc", "msg", "type"}
    unauthenticated = await api.get("/files/not-a-uuid")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json() == {"detail": "Not authenticated"}
    assert unauthenticated.headers["www-authenticate"] == "Bearer"
    repo.get_owned.assert_not_awaited()
    assert storage.calls == []


@pytest.mark.parametrize("path", ["/files", "/files/not-a-uuid"])
@pytest.mark.parametrize("header", [None, "Basic secret", "Bearer", "Bearer invalid"])
async def test_read_authentication_never_calls_file_repository(api, file_context, path, header):
    repo, storage = file_context
    repo.list_by_owner = AsyncMock(wraps=repo.list_by_owner)
    repo.get_owned = AsyncMock(wraps=repo.get_owned)
    response = await api.get(path, headers={"Authorization": header} if header else {})
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"
    repo.list_by_owner.assert_not_awaited()
    repo.get_owned.assert_not_awaited()
    assert storage.calls == []


@pytest.mark.parametrize("operation", ["list", "get"])
@pytest.mark.parametrize("unexpected", [False, True])
async def test_read_outages_are_sanitized(api, file_context, file_auth, operation, unexpected):
    repo, storage = file_context
    error = RuntimeError("private database secret") if unexpected else DependencyUnavailable()
    method = "list_by_owner" if operation == "list" else "get_owned"
    setattr(repo, method, AsyncMock(side_effect=error))
    response = await api.get(
        "/files" if operation == "list" else f"/files/{uuid4()}", headers=file_auth[1]
    )
    assert response.status_code == (500 if unexpected else 503)
    assert response.json() == {
        "detail": "Internal server error" if unexpected else "Service unavailable"
    }
    assert storage.calls == []
