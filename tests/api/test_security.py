"""Adversarial gaps beyond the existing token, size, privacy, and failure matrices."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.entities import User
from app.presentation.error_handlers import SanitizedServerErrors
from tests.unit.application.fakes import make_file


@pytest.mark.parametrize("path", ["/users", "/auth/login"])
async def test_unknown_json_field_names_cannot_echo_password(api, path, caplog):
    password = "private-password-sentinel-32"
    body = {"email": "alice@example.com", "password": password, password: "extra"}
    if path == "/users":
        body["name"] = "Alice"
    response = await api.post(path, json=body)
    assert response.status_code == 422
    assert password not in response.text
    assert password not in caplog.text
    assert all(set(error) == {"loc", "msg", "type"} for error in response.json()["detail"])


@pytest.mark.parametrize("field", ["owner_id", "storage_key", "bucket"])
async def test_client_cannot_choose_owner_or_private_storage_locator(
    api, file_context, file_auth, field, caplog
):
    private = "private-locator-sentinel"
    response = await api.post(
        "/files",
        headers=file_auth[1],
        files={"file": ("a", b"abc")},
        data={field: private},
    )
    assert response.status_code == 422
    assert private not in response.text
    assert private not in caplog.text
    assert file_context[1].calls == []
    assert await file_context[0].list_by_owner(file_auth[0].id) == []


async def test_failure_after_response_start_exposes_only_generic_exception():
    messages = []

    async def failing_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("private-streaming-credential")

    async def send(message):
        messages.append(message)

    async def receive():
        return {"type": "http.request", "body": b""}

    with pytest.raises(RuntimeError, match="^Response processing failed$") as caught:
        await SanitizedServerErrors(failing_app)({"type": "http"}, receive, send)
    assert caught.value.__suppress_context__
    assert len(messages) == 1


async def test_lifespan_failure_remains_visible_to_startup_operator():
    async def failing_app(scope, receive, send):
        raise RuntimeError("startup failed")

    with pytest.raises(RuntimeError, match="startup failed"):
        await SanitizedServerErrors(failing_app)({"type": "lifespan"}, None, None)


async def test_filename_matching_foreign_id_cannot_overwrite_or_delete_foreign_object(
    api, api_context, file_context, file_auth
):
    repo, storage = file_context
    owner, headers = file_auth
    other = User(
        uuid4(), "Bob", "bob@example.com", "private-hash", datetime(2026, 1, 1, tzinfo=UTC)
    )
    await api_context[1].add(other)
    foreign = make_file(other.id)
    await repo.add(foreign)
    await storage.upload(foreign.storage_key, b"foreign-private-bytes", foreign.content_type)
    response = await api.post(
        "/files",
        headers=headers,
        files={"file": (str(foreign.id), b"attacker-content")},
    )
    assert response.status_code == 201
    assert response.json()["id"] != str(foreign.id)
    assert storage.objects[foreign.storage_key] == (b"foreign-private-bytes", foreign.content_type)
    for method in (api.get, api.delete):
        denied = await method(
            f"/files/{foreign.id}",
            headers=headers,
            params={"user_id": str(other.id), "storage_key": foreign.storage_key},
        )
        assert denied.status_code == 404
    assert await repo.get_owned(foreign.id, other.id) == foreign
    assert storage.objects[foreign.storage_key][0] == b"foreign-private-bytes"
    assert len(await repo.list_by_owner(owner.id)) == 1


async def test_unknown_file_after_partial_foreign_spoof_never_mutates_storage(
    api, file_context, file_auth
):
    repo, storage = file_context
    repo.get_owned = AsyncMock(wraps=repo.get_owned)
    response = await api.delete(
        f"/files/{uuid4()}",
        headers=file_auth[1],
        params={"storage_key": "files/another-owner", "user_id": str(uuid4())},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "File not found"}
    assert storage.calls == []


async def test_unexpected_exception_cannot_escape_to_server_logging(
    api_context, file_context, file_auth, caplog
):
    from httpx import ASGITransport, AsyncClient

    private = "private-credential-from-unexpected-dependency"
    file_context[1].upload = AsyncMock(side_effect=RuntimeError(private))
    # A real ASGI server logs exceptions escaping the app. Strict transport exposes
    # that boundary instead of suppressing propagation after a 500 response.
    async with AsyncClient(
        transport=ASGITransport(api_context[0], raise_app_exceptions=True),
        base_url="http://test",
    ) as strict:
        response = await strict.post(
            "/files",
            headers=file_auth[1],
            files={"file": ("a", b"abc")},
        )
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert private not in response.text
    assert private not in caplog.text
