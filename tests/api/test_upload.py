from tempfile import SpooledTemporaryFile
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import starlette.formparsers

from app.domain.validation import MAX_FILE_SIZE


@pytest.fixture
def tracked_handles(monkeypatch):
    handles = []
    original = SpooledTemporaryFile

    def create(*args, **kwargs):
        handle = original(*args, **kwargs)
        handle.written_bytes = 0
        handle.max_write_bytes = 0
        original_write = handle.write

        def write(data):
            handle.written_bytes += len(data)
            handle.max_write_bytes = max(handle.max_write_bytes, len(data))
            return original_write(data)

        handle.write = write
        handles.append(handle)
        return handle

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", create)
    return handles


def multipart(payload, *, filename="file.bin", content_type=None, trailing=b""):
    type_header = f"Content-Type: {content_type}\r\n".encode() if content_type else b""
    return (
        (
            f'--boundary\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        ).encode()
        + type_header
        + b"\r\n"
        + payload
        + b"\r\n--boundary--\r\n"
        + trailing
    )


@pytest.mark.parametrize("size", [0, MAX_FILE_SIZE])
async def test_size_boundaries_safe_owned_metadata_and_closed_handles(
    api, file_context, file_auth, tracked_handles, size
):
    repo, storage = file_context
    owner, headers = file_auth
    response = await api.post(
        "/files",
        headers=headers,
        files={"file": ("example.bin", b"x" * size, "application/custom")},
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "filename", "content_type", "size_bytes", "created_at"}
    assert body["filename"] == "example.bin"
    assert body["size_bytes"] == size
    assert body["content_type"] == "application/custom"
    assert body["created_at"].endswith("Z")
    stored = await repo.get_owned(UUID(body["id"]), owner.id)
    assert stored is not None
    assert storage.objects == {stored.storage_key: (b"x" * size, "application/custom")}
    assert stored.storage_key not in response.text
    assert str(owner.id) not in response.text
    assert tracked_handles and all(handle.closed for handle in tracked_handles)
    assert tracked_handles[0]._rolled is (size > 1024 * 1024)
    assert tracked_handles[0].written_bytes == size
    assert tracked_handles[0].max_write_bytes <= 65536


async def test_missing_content_type_defaults(api, file_context, file_auth):
    response = await api.post(
        "/files",
        content=multipart(b"abc"),
        headers={**file_auth[1], "Content-Type": "multipart/form-data; boundary=boundary"},
    )
    assert response.status_code == 201
    assert response.json()["content_type"] == "application/octet-stream"


@pytest.mark.parametrize("filename", ["", "x" * 256, "a/b", "a\\b", "a\x01b"])
async def test_invalid_filename_has_no_side_effects(
    api, file_context, file_auth, tracked_handles, filename
):
    response = await api.post(
        "/files",
        content=multipart(b"content", filename=filename),
        headers={**file_auth[1], "Content-Type": "multipart/form-data; boundary=boundary"},
    )
    assert response.status_code == 422
    assert all(set(item) == {"loc", "msg", "type"} for item in response.json()["detail"])
    assert await file_context[0].list_by_owner(file_auth[0].id) == []
    assert file_context[1].calls == []
    assert all(handle.closed for handle in tracked_handles)


async def test_missing_file_is_422(api, file_context, file_auth):
    response = await api.post("/files", headers=file_auth[1])
    assert response.status_code == 422
    assert file_context[1].calls == []


@pytest.mark.parametrize("chunked", [False, True])
async def test_oversized_file_rejected_during_parsing(
    api, file_context, file_auth, tracked_handles, chunked
):
    raw = multipart(b"x" * (MAX_FILE_SIZE + 1))
    delivered = []

    async def chunks():
        for start in range(0, len(raw), 65536):
            delivered.append(start)
            yield raw[start : start + 65536]
        # Excess input must never be consumed after rejecting the file.
        delivered.append("tail")
        yield b"y" * 100000

    response = await api.post(
        "/files",
        content=chunks() if chunked else raw,
        headers={**file_auth[1], "Content-Type": "multipart/form-data; boundary=boundary"},
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "File too large"}
    assert file_context[1].calls == []
    assert await file_context[0].list_by_owner(file_auth[0].id) == []
    assert tracked_handles and all(handle.closed for handle in tracked_handles)
    assert all(handle.written_bytes <= MAX_FILE_SIZE for handle in tracked_handles)
    assert all(handle.max_write_bytes <= 65536 for handle in tracked_handles)
    if chunked:
        assert "tail" not in delivered


@pytest.mark.parametrize("authorization", [None, "Basic bad", "Bearer bad", "Bearer"])
async def test_authentication_precedes_multipart_parsing(
    api, file_context, tracked_handles, authorization
):
    headers = {"Content-Type": "multipart/form-data; boundary=boundary"}
    if authorization:
        headers["Authorization"] = authorization
    response = await api.post("/files", content=b"malformed private multipart", headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert file_context[1].calls == []
    assert tracked_handles == []


async def test_owner_override_and_multiple_files_rejected(
    api, file_context, file_auth, tracked_handles
):
    for form in (
        {"data": {"user_id": str(uuid4())}, "files": {"file": ("a", b"abc")}},
        {"files": [("file", ("a", b"abc")), ("file", ("b", b"def"))]},
    ):
        response = await api.post("/files", headers=file_auth[1], **form)
        assert response.status_code == 422
    assert file_context[1].calls == []
    assert all(handle.closed for handle in tracked_handles)


@pytest.mark.parametrize("failure", ["storage", "metadata", "cleanup", "unexpected"])
async def test_dependency_failures_are_sanitized_and_close_handles(
    api, file_context, file_auth, tracked_handles, failure
):
    repo, storage = file_context
    if failure == "storage":
        storage.fail_upload = True
    elif failure in ("metadata", "cleanup"):
        repo.fail_writes = True
        storage.fail_delete = failure == "cleanup"
    else:
        storage.upload = AsyncMock(side_effect=RuntimeError("private AWS credential"))
    response = await api.post("/files", headers=file_auth[1], files={"file": ("a", b"abc")})
    assert response.status_code == (500 if failure == "unexpected" else 503)
    assert response.json() == {
        "detail": "Internal server error" if failure == "unexpected" else "Service unavailable"
    }
    assert await repo.list_by_owner(file_auth[0].id) == []
    assert bool(storage.objects) is (failure == "cleanup")
    assert tracked_handles and all(handle.closed for handle in tracked_handles)


async def test_truncated_and_large_header_requests_close_handles(
    api, file_context, file_auth, tracked_handles
):
    for raw in (
        multipart(b"abc")[:-18],
        multipart(b"abc", content_type="x" * 20000),
    ):
        response = await api.post(
            "/files",
            content=raw,
            headers={**file_auth[1], "Content-Type": "multipart/form-data; boundary=boundary"},
        )
        assert response.status_code == 422
    assert file_context[1].calls == []
    assert all(handle.closed for handle in tracked_handles)


@pytest.mark.parametrize("size", [0, MAX_FILE_SIZE])
async def test_chunked_valid_upload_without_content_length(api, file_context, file_auth, size):
    raw = multipart(b"x" * size)

    async def chunks():
        for start in range(0, len(raw), 65536):
            yield raw[start : start + 65536]

    response = await api.post(
        "/files",
        content=chunks(),
        headers={**file_auth[1], "Content-Type": "multipart/form-data; boundary=boundary"},
    )
    assert response.status_code == 201
    assert response.json()["size_bytes"] == size


@pytest.mark.parametrize("scenario", ["expired", "unknown_user"])
async def test_expired_or_unknown_user_token_never_parses_file(
    api, api_context, file_context, file_auth, tracked_handles, scenario
):
    from datetime import timedelta

    tokens = api_context[3]
    if scenario == "unknown_user":
        token = await tokens.issue(uuid4())
        headers = {"Authorization": f"Bearer {token.access_token}"}
    else:
        current = tokens.clock()
        tokens.clock = lambda: current + timedelta(hours=2)
        headers = file_auth[1]
    response = await api.post("/files", headers=headers, files={"file": ("a", b"abc")})
    assert response.status_code == 401
    assert tracked_handles == []
    assert file_context[1].calls == []


async def test_authenticated_malformed_multipart_is_sanitized(
    api, file_context, file_auth, tracked_handles
):
    response = await api.post(
        "/files",
        content=b"private-password-not-multipart",
        headers={**file_auth[1], "Content-Type": "multipart/form-data; boundary=boundary"},
    )
    assert response.status_code == 422
    assert "private-password" not in response.text
    assert file_context[1].calls == []
    assert all(handle.closed for handle in tracked_handles)
