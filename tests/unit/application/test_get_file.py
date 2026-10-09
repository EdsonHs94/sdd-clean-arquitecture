import inspect
from dataclasses import asdict
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.errors import DependencyUnavailable, FileNotFound
from app.application.use_cases.get_user_file import GetUserFile
from tests.unit.application.fakes import FakeFileRepository, make_file


async def test_owned_success_returns_only_safe_metadata():
    repo, owner = FakeFileRepository(), uuid4()
    file = make_file(owner)
    await repo.add(file)
    repo.get_owned = AsyncMock(wraps=repo.get_owned)
    result = await GetUserFile(repo).execute(owner, file.id)
    repo.get_owned.assert_awaited_once_with(file.id, owner)
    assert asdict(result) == {
        "id": file.id,
        "filename": file.original_name,
        "content_type": file.content_type,
        "size_bytes": file.size,
        "created_at": file.created_at,
    }
    assert str(owner) not in repr(result)
    assert file.storage_key not in repr(result)


async def test_missing_and_foreign_failures_are_indistinguishable():
    repo, owner, foreign = FakeFileRepository(), uuid4(), uuid4()
    file = make_file(owner)
    await repo.add(file)
    errors = []
    for requested in (file.id, uuid4()):
        with pytest.raises(FileNotFound) as raised:
            await GetUserFile(repo).execute(foreign, requested)
        errors.append(raised.value)
    assert type(errors[0]) is FileNotFound
    assert type(errors[0]) is type(errors[1])
    assert str(errors[0]) == str(errors[1]) == "File not found"
    assert await repo.get_owned(file.id, owner) == file


async def test_repository_outage_is_distinct_from_not_found():
    repo = FakeFileRepository(fail_reads=True)
    with pytest.raises(DependencyUnavailable, match="^Service unavailable$"):
        await GetUserFile(repo).execute(uuid4(), uuid4())


async def test_has_no_storage_dependency_or_read():
    assert list(inspect.signature(GetUserFile).parameters) == ["repository"]
    repo, owner = FakeFileRepository(), uuid4()
    file = make_file(owner)
    await repo.add(file)
    # A repository-only instance succeeds; no object-storage adapter is supplied.
    assert (await GetUserFile(repo).execute(owner, file.id)).id == file.id
