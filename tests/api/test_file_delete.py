from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from tests.unit.application.fakes import make_file


async def seed_file(file_context, owner):
    repo, storage = file_context
    file = make_file(owner)
    await repo.add(file)
    await storage.upload(file.storage_key, b"abc", file.content_type)
    storage.calls.clear()
    return file


async def test_empty_204_and_repeat_404(api, file_context, file_auth):
    repo, storage = file_context
    owner, headers = file_auth
    file = await seed_file(file_context, owner.id)
    response = await api.delete(f"/files/{file.id}", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert await repo.get_owned(file.id, owner.id) is None
    assert storage.objects == {}
    repeated = await api.delete(f"/files/{file.id}", headers=headers)
    assert repeated.status_code == 404
    assert repeated.json() == {"detail": "File not found"}
    assert storage.calls == [("delete", file.storage_key)]


async def test_foreign_missing_identical_without_storage_calls(api, file_context, file_auth):
    repo, storage = file_context
    file = await seed_file(file_context, uuid4())
    for file_id in (file.id, uuid4()):
        response = await api.delete(f"/files/{file_id}", headers=file_auth[1])
        assert response.status_code == 404
        assert response.json() == {"detail": "File not found"}
    assert storage.calls == []
    assert await repo.get_owned(file.id, file.user_id) == file
    assert file.storage_key in storage.objects


async def test_malformed_uuid_auth_precedence(api, file_context, file_auth):
    repo, storage = file_context
    repo.get_owned = AsyncMock(wraps=repo.get_owned)
    invalid = await api.delete("/files/not-a-uuid", headers=file_auth[1])
    assert invalid.status_code == 422
    (detail,) = invalid.json()["detail"]
    assert detail["loc"] == ["path", "file_id"]
    assert set(detail) == {"loc", "msg", "type"}
    unauthenticated = await api.delete("/files/not-a-uuid")
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["www-authenticate"] == "Bearer"
    repo.get_owned.assert_not_awaited()
    assert storage.calls == []


@pytest.mark.parametrize("header", [None, "Basic bad", "Bearer", "Bearer invalid"])
async def test_unauthorized_never_calls_file_dependencies(api, file_context, header):
    repo, storage = file_context
    repo.get_owned = AsyncMock(wraps=repo.get_owned)
    response = await api.delete(
        f"/files/{uuid4()}", headers={"Authorization": header} if header else {}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"
    repo.get_owned.assert_not_awaited()
    assert storage.calls == []


@pytest.mark.parametrize("failure", ["storage", "metadata"])
async def test_failure_preserves_metadata_and_retry_succeeds(api, file_context, file_auth, failure):
    repo, storage = file_context
    owner, headers = file_auth
    file = await seed_file(file_context, owner.id)
    storage.fail_delete = failure == "storage"
    repo.fail_writes = failure == "metadata"
    response = await api.delete(f"/files/{file.id}", headers=headers)
    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}
    assert await repo.get_owned(file.id, owner.id) == file
    assert (file.storage_key in storage.objects) is (failure == "storage")
    storage.fail_delete = repo.fail_writes = False
    retry = await api.delete(f"/files/{file.id}", headers=headers)
    assert retry.status_code == 204
    assert retry.content == b""
    assert await repo.get_owned(file.id, owner.id) is None
    assert storage.objects == {}


@pytest.mark.parametrize("unexpected", [False, True])
async def test_lookup_outage_does_not_touch_storage(api, file_context, file_auth, unexpected):
    from app.application.errors import DependencyUnavailable

    repo, storage = file_context
    repo.get_owned = AsyncMock(
        side_effect=(
            RuntimeError("private database key") if unexpected else DependencyUnavailable()
        )
    )
    response = await api.delete(f"/files/{uuid4()}", headers=file_auth[1])
    assert response.status_code == (500 if unexpected else 503)
    assert response.json() == {
        "detail": "Internal server error" if unexpected else "Service unavailable"
    }
    assert storage.calls == []
