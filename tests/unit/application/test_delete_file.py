import asyncio
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.application.errors import DependencyUnavailable, FileNotFound
from app.application.use_cases.delete_user_file import DeleteUserFile
from tests.unit.application.fakes import FakeFileRepository, FakeFileStorage, make_file


async def setup_file():
    repo, storage, owner = FakeFileRepository(), FakeFileStorage(), uuid4()
    file = make_file(owner)
    await repo.add(file)
    await storage.upload(file.storage_key, b"abc", file.content_type)
    storage.calls.clear()
    return repo, storage, owner, file


async def test_success_deletes_content_before_committed_metadata_and_repeat_is_absent():
    repo, storage, owner, file = await setup_file()
    events = Mock()
    storage.delete = AsyncMock(wraps=storage.delete)
    repo.delete_owned = AsyncMock(wraps=repo.delete_owned)
    events.attach_mock(storage.delete, "storage")
    events.attach_mock(repo.delete_owned, "metadata")
    use_case = DeleteUserFile(repo, storage)
    assert await use_case.execute(owner, file.id) is None
    assert [call[0] for call in events.mock_calls] == ["storage", "metadata"]
    assert await repo.get_owned(file.id, owner) is None
    assert storage.objects == {}
    with pytest.raises(FileNotFound):
        await use_case.execute(owner, file.id)
    assert storage.delete.await_count == 1


async def test_foreign_and_missing_do_not_touch_storage():
    repo, storage, owner, file = await setup_file()
    for user_id, file_id in ((uuid4(), file.id), (owner, uuid4())):
        with pytest.raises(FileNotFound, match="^File not found$"):
            await DeleteUserFile(repo, storage).execute(user_id, file_id)
    assert storage.calls == []
    assert await repo.get_owned(file.id, owner) == file


async def test_storage_failure_preserves_metadata_without_attempting_delete():
    repo, storage, owner, file = await setup_file()
    storage.fail_delete = True
    repo.delete_owned = AsyncMock(wraps=repo.delete_owned)
    with pytest.raises(DependencyUnavailable):
        await DeleteUserFile(repo, storage).execute(owner, file.id)
    repo.delete_owned.assert_not_awaited()
    assert await repo.get_owned(file.id, owner) == file
    assert file.storage_key in storage.objects


async def test_metadata_failure_is_retryable_with_absent_content():
    repo, storage, owner, file = await setup_file()
    repo.fail_writes = True
    use_case = DeleteUserFile(repo, storage)
    with pytest.raises(DependencyUnavailable):
        await use_case.execute(owner, file.id)
    assert storage.objects == {}
    assert await repo.get_owned(file.id, owner) == file
    repo.fail_writes = False
    await use_case.execute(owner, file.id)
    assert await repo.get_owned(file.id, owner) is None
    assert storage.calls == [("delete", file.storage_key)] * 2


async def test_concurrent_delete_never_reports_success_with_metadata_remaining():
    repo, storage, owner, file = await setup_file()
    unrelated = make_file(uuid4(), 2)
    await repo.add(unrelated)
    await storage.upload(unrelated.storage_key, b"abc", unrelated.content_type)
    storage.calls.clear()
    # Both lookups see the same row before either deletion completes.
    barrier = asyncio.Barrier(2)
    original = repo.get_owned

    async def overlapping_lookup(file_id, user_id):
        result = await original(file_id, user_id)
        await barrier.wait()
        return result

    repo.get_owned = overlapping_lookup
    use_case = DeleteUserFile(repo, storage)
    results = await asyncio.gather(
        use_case.execute(owner, file.id),
        use_case.execute(owner, file.id),
        return_exceptions=True,
    )
    assert results.count(None) == 1
    assert sum(isinstance(result, FileNotFound) for result in results) == 1
    assert await original(file.id, owner) is None
    assert await original(unrelated.id, unrelated.user_id) == unrelated
    assert storage.objects == {unrelated.storage_key: (b"abc", unrelated.content_type)}
    assert storage.calls == [("delete", file.storage_key)] * 2


async def test_lookup_outage_never_touches_storage():
    repo, storage, owner, file = await setup_file()
    repo.fail_reads = True
    with pytest.raises(DependencyUnavailable):
        await DeleteUserFile(repo, storage).execute(owner, file.id)
    assert storage.calls == []
