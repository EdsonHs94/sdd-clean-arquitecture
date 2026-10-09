import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.errors import DependencyUnavailable
from tests.unit.application.fakes import FakeFileRepository, make_file


async def test_owned_operations_and_absent_foreign_equivalence():
    repo = FakeFileRepository()
    owner, foreign = uuid4(), uuid4()
    file = make_file(owner)
    await repo.add(file)
    assert await repo.get_owned(file.id, owner) == file
    for file_id in (file.id, uuid4()):
        assert await repo.get_owned(file_id, foreign) is None
        assert await repo.delete_owned(file_id, foreign) is False
    assert await repo.list_by_owner(foreign) == []
    assert await repo.list_by_owner(owner) == [file]
    assert await repo.delete_owned(file.id, owner) is True
    assert await repo.get_owned(file.id, owner) is None


async def test_order_by_time_then_uuid():
    repo, owner = FakeFileRepository(), uuid4()
    earlier = make_file(owner, 3, datetime(2025, 1, 1, tzinfo=UTC))
    first, second = make_file(owner, 1), make_file(owner, 2)
    for file in (second, earlier, first):
        await repo.add(file)
    assert await repo.list_by_owner(owner) == [earlier, first, second]


async def test_failed_commits_preserve_state():
    repo, owner = FakeFileRepository(), uuid4()
    original, new = make_file(owner), make_file(owner, 2)
    await repo.add(original)
    repo.fail_writes = True
    with pytest.raises(DependencyUnavailable):
        await repo.add(new)
    with pytest.raises(DependencyUnavailable):
        await repo.delete_owned(original.id, owner)
    assert await repo.list_by_owner(owner) == [original]


async def test_concurrent_delete_returns_one_removed_row():
    repo, owner = FakeFileRepository(), uuid4()
    file = make_file(owner)
    await repo.add(file)
    assert sorted(
        await asyncio.gather(repo.delete_owned(file.id, owner), repo.delete_owned(file.id, owner))
    ) == [False, True]


async def test_read_outages_and_duplicate_identity():
    repo, owner = FakeFileRepository(), uuid4()
    file = make_file(owner)
    await repo.add(file)
    with pytest.raises(DependencyUnavailable):
        await repo.add(file)
    repo.fail_reads = True
    for operation in (repo.list_by_owner(owner), repo.get_owned(file.id, owner)):
        with pytest.raises(DependencyUnavailable):
            await operation
