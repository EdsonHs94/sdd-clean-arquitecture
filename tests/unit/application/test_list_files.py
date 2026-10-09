from dataclasses import asdict
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.errors import DependencyUnavailable
from app.application.use_cases.list_user_files import ListUserFiles
from tests.unit.application.fakes import FakeFileRepository, make_file


async def test_list_isolates_two_authenticated_owners_and_empty_owner():
    repo = FakeFileRepository()
    owner, foreign = uuid4(), uuid4()
    own, other = make_file(owner, 1), make_file(foreign, 2)
    await repo.add(own)
    await repo.add(other)
    repo.list_by_owner = AsyncMock(wraps=repo.list_by_owner)
    use_case = ListUserFiles(repo)
    assert [file.id for file in await use_case.execute(owner)] == [own.id]
    repo.list_by_owner.assert_awaited_once_with(owner)
    assert [file.id for file in await use_case.execute(foreign)] == [other.id]
    assert await use_case.execute(uuid4()) == []


async def test_ordering_by_creation_time_and_uuid():
    repo, owner = FakeFileRepository(), uuid4()
    earlier = make_file(owner, 3, datetime(2025, 1, 1, tzinfo=UTC))
    first, second = make_file(owner, 1), make_file(owner, 2)
    for file in (second, first, earlier):
        await repo.add(file)
    assert [file.id for file in await ListUserFiles(repo).execute(owner)] == [
        earlier.id,
        first.id,
        second.id,
    ]


async def test_safe_metadata_projection():
    repo, owner = FakeFileRepository(), uuid4()
    file = make_file(owner)
    await repo.add(file)
    (result,) = await ListUserFiles(repo).execute(owner)
    assert asdict(result) == {
        "id": file.id,
        "filename": file.original_name,
        "content_type": file.content_type,
        "size_bytes": file.size,
        "created_at": file.created_at,
    }
    assert file.storage_key not in repr(result)
    assert str(owner) not in repr(result)


async def test_repository_outage_propagates():
    repo = FakeFileRepository(fail_reads=True)
    with pytest.raises(DependencyUnavailable, match="^Service unavailable$"):
        await ListUserFiles(repo).execute(uuid4())
