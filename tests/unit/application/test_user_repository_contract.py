import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.errors import DependencyUnavailable, EmailAlreadyRegistered
from app.application.ports import UserRepository
from app.domain.entities import User
from tests.unit.application.fakes import FakeUserRepository


def make_user(email="alice@example.com"):
    return User(
        id=uuid4(),
        name="Alice",
        email=email,
        password_hash="private-hash",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


async def read_user(repository: UserRepository, user: User) -> User | None:
    return await repository.get_by_id(user.id)


async def test_fake_is_usable_through_repository_port():
    repository = FakeUserRepository()
    user = make_user()
    assert await repository.add(user) is None
    assert await read_user(repository, user) == user
    assert await repository.get_by_email(user.email) == user


async def test_missing_user_returns_none():
    repository = FakeUserRepository()
    assert await repository.get_by_id(uuid4()) is None
    assert await repository.get_by_email("missing@example.com") is None


async def test_normalized_duplicate_email_preserves_original_user():
    repository = FakeUserRepository()
    first = make_user()
    duplicate = make_user(" ALICE@EXAMPLE.COM ")
    await repository.add(first)
    with pytest.raises(EmailAlreadyRegistered):
        await repository.add(duplicate)
    assert await repository.get_by_email(first.email) == first
    assert await repository.get_by_id(duplicate.id) is None


async def test_concurrent_duplicate_add_has_only_one_success():
    repository = FakeUserRepository()
    users = [make_user(), make_user()]
    results = await asyncio.gather(
        *(repository.add(user) for user in users), return_exceptions=True
    )
    assert results.count(None) == 1
    assert sum(isinstance(result, EmailAlreadyRegistered) for result in results) == 1
    stored = [await repository.get_by_id(user.id) for user in users]
    assert sum(user is not None for user in stored) == 1


async def test_failed_write_does_not_mutate_existing_state():
    repository = FakeUserRepository()
    first, second = make_user(), make_user("bob@example.com")
    await repository.add(first)
    repository.fail_writes = True
    with pytest.raises(DependencyUnavailable):
        await repository.add(second)
    repository.fail_writes = False
    assert await repository.get_by_id(first.id) == first
    assert await repository.get_by_id(second.id) is None
    assert await repository.get_by_email(second.email) is None


@pytest.mark.parametrize("operation", ["get_by_email", "get_by_id"])
async def test_read_failure_is_distinct_from_missing_user(operation):
    repository = FakeUserRepository()
    repository.fail_reads = True
    argument = "alice@example.com" if operation == "get_by_email" else uuid4()
    with pytest.raises(DependencyUnavailable):
        await getattr(repository, operation)(argument)


async def test_fake_representation_does_not_expose_password_hash():
    repository = FakeUserRepository()
    await repository.add(make_user())
    assert "private-hash" not in repr(repository)
