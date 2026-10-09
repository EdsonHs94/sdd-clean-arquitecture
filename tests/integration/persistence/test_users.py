import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.application.errors import DependencyUnavailable, EmailAlreadyRegistered
from app.domain.entities import User
from app.infrastructure.persistence.user_repository import SqlAlchemyUserRepository

pytestmark = pytest.mark.integration


def make_user(email="alice@example.com", *, user_id=None):
    return User(
        id=user_id or uuid4(),
        name="Alice",
        email=email,
        password_hash="private-hash",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


async def test_add_commits_and_maps_to_domain_after_session_closes(database):
    user = make_user()
    async with database.session_factory() as session:
        repository = SqlAlchemyUserRepository(session)
        assert await repository.add(user) is None
    async with database.session_factory() as session:
        repository = SqlAlchemyUserRepository(session)
        stored = await repository.get_by_id(user.id)
        assert isinstance(stored, User)
        assert stored == user
        assert await repository.get_by_email(user.email) == user
    assert stored.email == user.email
    assert "private-hash" not in repr(stored)


async def test_missing_user_returns_none(database):
    async with database.session_factory() as session:
        repository = SqlAlchemyUserRepository(session)
        assert await repository.get_by_id(uuid4()) is None
        assert await repository.get_by_email("missing@example.com") is None


async def test_duplicate_normalized_email_rolls_back_and_session_is_reusable(database):
    first, second = make_user(), make_user(" ALICE@EXAMPLE.COM ")
    async with database.session_factory() as session:
        repository = SqlAlchemyUserRepository(session)
        await repository.add(first)
        with pytest.raises(EmailAlreadyRegistered):
            await repository.add(second)
        assert await repository.get_by_id(second.id) is None
        await repository.add(make_user("bob@example.com"))
        assert await repository.get_by_email(first.email) == first


async def test_concurrent_duplicate_inserts_have_one_committed_winner(database):
    users = [make_user(), make_user()]

    async def insert(user):
        async with database.session_factory() as session:
            await SqlAlchemyUserRepository(session).add(user)

    results = await asyncio.gather(*(insert(user) for user in users), return_exceptions=True)
    assert results.count(None) == 1
    assert sum(isinstance(error, EmailAlreadyRegistered) for error in results) == 1
    async with database.session_factory() as session:
        repository = SqlAlchemyUserRepository(session)
        found = [await repository.get_by_id(user.id) for user in users]
        assert sum(user is not None for user in found) == 1


async def test_primary_key_violation_is_not_duplicate_email_and_rolls_back(database):
    first = make_user()
    second = make_user("bob@example.com", user_id=first.id)
    async with database.session_factory() as session:
        repository = SqlAlchemyUserRepository(session)
        await repository.add(first)
        with pytest.raises(DependencyUnavailable):
            await repository.add(second)
        assert await repository.get_by_id(first.id) == first
        assert await repository.get_by_email(second.email) is None


async def test_commit_failure_rolls_back_uncommitted_rows(database, monkeypatch):
    user = make_user()
    async with database.session_factory() as session:
        repository = SqlAlchemyUserRepository(session)
        real_commit = session.commit

        async def fail_commit():
            await session.flush()
            raise OperationalError("commit", {}, RuntimeError("private database details"))

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(DependencyUnavailable):
            await repository.add(user)
        monkeypatch.setattr(session, "commit", real_commit)
        assert await repository.get_by_id(user.id) is None
        await repository.add(user)
    async with database.session_factory() as session:
        assert await SqlAlchemyUserRepository(session).get_by_id(user.id) == user


@pytest.mark.parametrize("method", ["get_by_email", "get_by_id"])
@pytest.mark.parametrize("failure", ["query", "connection"])
async def test_read_failure_is_sanitized(database, method, failure, monkeypatch):
    async with database.session_factory() as session:
        failure_error = (
            OperationalError("private query", {}, RuntimeError("private connection"))
            if failure == "query"
            else ConnectionRefusedError("private connection")
        )
        monkeypatch.setattr(
            session,
            "execute",
            AsyncMock(side_effect=failure_error),
        )
        argument = "alice@example.com" if method == "get_by_email" else uuid4()
        with pytest.raises(DependencyUnavailable) as error:
            await getattr(SqlAlchemyUserRepository(session), method)(argument)
        assert str(error.value) == "Service unavailable"
        assert error.value.__suppress_context__


async def test_database_session_rolls_back_on_exception_and_returns_connection(database):
    with pytest.raises(RuntimeError, match="consumer failed"):
        async with database.session() as session:
            await session.execute(text("SELECT 1"))
            raise RuntimeError("consumer failed")
    assert database.engine.sync_engine.pool.checkedout() == 0
    async with database.session() as session:
        assert await session.scalar(text("SELECT 1")) == 1
    assert database.engine.sync_engine.pool.checkedout() == 0


async def test_database_close_disposes_idle_connections(database):
    async with database.session_factory() as session:
        await session.execute(text("SELECT 1"))
    pool = database.engine.sync_engine.pool
    await database.close()
    assert database.engine.sync_engine.pool is not pool
