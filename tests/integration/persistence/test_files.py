import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.application.errors import DependencyUnavailable
from app.domain.entities import User
from app.infrastructure.persistence.file_repository import SqlAlchemyFileRepository
from app.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from tests.unit.application.fakes import make_file

pytestmark = pytest.mark.integration


async def seed_owner(database):
    owner = User(
        uuid4(), "Alice", f"{uuid4().hex}@example.com", "hash", datetime(2026, 1, 1, tzinfo=UTC)
    )
    async with database.session() as session:
        await SqlAlchemyUserRepository(session).add(owner)
    return owner.id


async def test_committed_roundtrip_owner_filters_and_order(database):
    owner, other = await seed_owner(database), await seed_owner(database)
    first, second = make_file(owner, 1), make_file(owner, 2)
    early = make_file(owner, 3, datetime(2025, 1, 1, tzinfo=UTC))
    foreign = make_file(other, 4)
    async with database.session() as session:
        repo = SqlAlchemyFileRepository(session)
        for file in (second, foreign, first, early):
            await repo.add(file)
    async with database.session() as session:
        repo = SqlAlchemyFileRepository(session)
        assert await repo.list_by_owner(owner) == [early, first, second]
        assert await repo.list_by_owner(uuid4()) == []
        assert await repo.get_owned(first.id, owner) == first
        assert await repo.get_owned(first.id, other) is None
        assert await repo.get_owned(uuid4(), owner) is None
        assert await repo.delete_owned(first.id, other) is False
        assert await repo.delete_owned(first.id, owner) is True
        assert await repo.delete_owned(first.id, owner) is False
    async with database.session() as session:
        repo = SqlAlchemyFileRepository(session)
        assert await repo.get_owned(first.id, owner) is None
        assert await repo.get_owned(foreign.id, other) == foreign


async def test_foreign_key_and_unique_storage_key_rollback(database):
    owner = await seed_owner(database)
    file = make_file(owner)
    async with database.session() as session:
        repo = SqlAlchemyFileRepository(session)
        with pytest.raises(DependencyUnavailable):
            await repo.add(replace(file, user_id=uuid4()))
        await repo.add(file)
        with pytest.raises(DependencyUnavailable):
            await repo.add(replace(file, id=uuid4()))
        assert await repo.list_by_owner(owner) == [file]


@pytest.mark.parametrize("size", [-1, 10485761])
async def test_database_size_constraint_rejects_invalid_raw_write(database, size):
    owner = await seed_owner(database)
    # Bypass domain validation to prove the actual database constraint.
    async with database.session() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text("""
                INSERT INTO files
                (id, user_id, original_name, storage_key, content_type, size, created_at)
                VALUES (:id, :owner, 'file', 'key', 'text/plain', :size, now())
            """),
                {"id": uuid4(), "owner": owner, "size": size},
            )
        await session.rollback()


@pytest.mark.parametrize("operation", ["add", "delete"])
async def test_commit_failure_rolls_back_and_reuses_session(database, monkeypatch, operation):
    owner = await seed_owner(database)
    file = make_file(owner)
    async with database.session() as session:
        repo = SqlAlchemyFileRepository(session)
        if operation == "delete":
            await repo.add(file)
        real_commit = session.commit

        async def fail_commit():
            await session.flush()
            raise OperationalError("commit", {}, RuntimeError("private details"))

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(DependencyUnavailable, match="^Service unavailable$"):
            if operation == "add":
                await repo.add(file)
            else:
                await repo.delete_owned(file.id, owner)
        monkeypatch.setattr(session, "commit", real_commit)
        assert await repo.get_owned(file.id, owner) == (file if operation == "delete" else None)
        if operation == "add":
            await repo.add(file)
        else:
            assert await repo.delete_owned(file.id, owner) is True


async def test_concurrent_delete_removes_exactly_one_owned_row(database):
    owner = await seed_owner(database)
    file, other = make_file(owner), make_file(owner, 2)
    async with database.session() as session:
        repo = SqlAlchemyFileRepository(session)
        await repo.add(file)
        await repo.add(other)

    async def remove():
        async with database.session() as session:
            return await SqlAlchemyFileRepository(session).delete_owned(file.id, owner)

    assert sorted(await asyncio.gather(remove(), remove())) == [False, True]
    async with database.session() as session:
        assert await SqlAlchemyFileRepository(session).list_by_owner(owner) == [other]


@pytest.mark.parametrize("operation", ["list", "get", "delete"])
async def test_query_failures_are_sanitized(database, monkeypatch, operation):
    async with database.session() as session:
        monkeypatch.setattr(
            session,
            "execute",
            AsyncMock(
                side_effect=OperationalError("private query", {}, RuntimeError("private details"))
            ),
        )
        repo, owner, file_id = SqlAlchemyFileRepository(session), uuid4(), uuid4()
        with pytest.raises(DependencyUnavailable) as error:
            if operation == "list":
                await repo.list_by_owner(owner)
            elif operation == "get":
                await repo.get_owned(file_id, owner)
            else:
                await repo.delete_owned(file_id, owner)
        assert str(error.value) == "Service unavailable"
        assert error.value.__suppress_context__
