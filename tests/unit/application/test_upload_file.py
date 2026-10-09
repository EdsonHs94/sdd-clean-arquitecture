from dataclasses import asdict
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.application.errors import DependencyUnavailable
from app.application.use_cases.upload_file import UploadFile
from app.domain.errors import FileTooLarge, InvalidFileData
from app.domain.validation import MAX_FILE_SIZE
from tests.unit.application.fakes import FakeFileRepository, FakeFileStorage


@pytest.fixture
def dependencies():
    return FakeFileRepository(), FakeFileStorage()


async def test_success_uses_authenticated_owner_and_safe_metadata(dependencies):
    repo, storage = dependencies
    owner, file_id = uuid4(), uuid4()
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    result = await UploadFile(
        repo, storage, clock=lambda: created_at, id_factory=lambda: file_id
    ).execute(owner, "private-name.txt", b"private content", "text/plain")
    stored = await repo.get_owned(file_id, owner)
    assert stored.user_id == owner
    assert stored.created_at == created_at
    assert stored.storage_key == f"files/{file_id}"
    assert storage.objects == {stored.storage_key: (b"private content", "text/plain")}
    assert asdict(result) == {
        "id": file_id,
        "filename": "private-name.txt",
        "content_type": "text/plain",
        "size_bytes": 15,
        "created_at": created_at,
    }
    assert str(owner) not in repr(result)
    assert stored.storage_key not in repr(result)


async def test_repeated_filenames_have_distinct_opaque_keys(dependencies):
    repo, storage = dependencies
    owner = uuid4()
    use_case = UploadFile(repo, storage)
    first = await use_case.execute(owner, "same.txt", b"one")
    second = await use_case.execute(owner, "same.txt", b"two")
    assert first.id != second.id
    assert len(storage.objects) == 2
    assert all("same.txt" not in key for key in storage.objects)
    assert [f.original_name for f in await repo.list_by_owner(owner)] == ["same.txt"] * 2


@pytest.mark.parametrize("size", [0, MAX_FILE_SIZE])
async def test_size_boundaries_and_default_content_type(dependencies, size):
    repo, storage = dependencies
    owner = uuid4()
    result = await UploadFile(repo, storage).execute(owner, "file", b"x" * size)
    assert result.size_bytes == size
    assert result.content_type == "application/octet-stream"
    assert len(next(iter(storage.objects.values()))[0]) == size
    assert len(await repo.list_by_owner(owner)) == 1


@pytest.mark.parametrize("filename", ["", "x" * 256, "a/b", "a\\b", "a\x00b", "a\nb"])
async def test_invalid_filename_has_no_side_effects(dependencies, filename):
    repo, storage = dependencies
    owner = uuid4()
    with pytest.raises(InvalidFileData):
        await UploadFile(repo, storage).execute(owner, filename, b"content")
    assert storage.calls == []
    assert await repo.list_by_owner(owner) == []


async def test_oversized_upload_has_no_side_effects(dependencies):
    repo, storage = dependencies
    owner = uuid4()
    with pytest.raises(FileTooLarge):
        await UploadFile(repo, storage).execute(owner, "file", b"x" * (MAX_FILE_SIZE + 1))
    assert storage.calls == []
    assert await repo.list_by_owner(owner) == []


async def test_storage_failure_does_not_attempt_metadata_write(dependencies):
    repo, storage = dependencies
    storage.fail_upload = True
    repo.add = AsyncMock(wraps=repo.add)
    owner = uuid4()
    with pytest.raises(DependencyUnavailable):
        await UploadFile(repo, storage).execute(owner, "file", b"content")
    repo.add.assert_not_awaited()
    assert storage.objects == {}
    assert await repo.list_by_owner(owner) == []
    assert [operation for operation, _ in storage.calls] == ["upload"]


@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_persistence_failure_compensates_in_order_and_preserves_error(
    dependencies, cleanup_fails, caplog
):
    repo, storage = dependencies
    owner, file_id = uuid4(), uuid4()
    original_error = DependencyUnavailable()
    storage.fail_delete = cleanup_fails
    repo.add = AsyncMock(side_effect=original_error)
    events = Mock()
    storage.upload = AsyncMock(wraps=storage.upload)
    storage.delete = AsyncMock(wraps=storage.delete)
    events.attach_mock(storage.upload, "upload")
    events.attach_mock(repo.add, "add")
    events.attach_mock(storage.delete, "delete")
    with pytest.raises(DependencyUnavailable) as raised:
        await UploadFile(repo, storage, id_factory=lambda: file_id).execute(
            owner, "private-filename", b"sensitive bytes", "private/type"
        )
    assert raised.value is original_error
    assert [call[0] for call in events.mock_calls] == ["upload", "add", "delete"]
    assert await repo.list_by_owner(owner) == []
    key = f"files/{file_id}"
    assert storage.objects == ({key: (b"sensitive bytes", "private/type")} if cleanup_fails else {})
    if cleanup_fails:
        assert "cleanup" in caplog.text.lower()
        assert str(file_id) in caplog.text
        for private in (key, str(owner), "private-filename", "sensitive bytes", "private/type"):
            assert private not in caplog.text
    else:
        assert caplog.records == []
