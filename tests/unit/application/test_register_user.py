from dataclasses import asdict
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.errors import DependencyUnavailable, EmailAlreadyRegistered
from app.application.use_cases.register_user import RegisterUser
from app.domain.entities import User
from app.domain.errors import InvalidUserData
from tests.unit.application.fakes import FakePasswordHasher, FakeUserRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PASSWORD = "  secure password  "


@pytest.fixture
def dependencies():
    return FakeUserRepository(), FakePasswordHasher()


async def test_registration_persists_hash_and_returns_only_safe_profile(dependencies, caplog):
    repository, hasher = dependencies
    user_id = uuid4()
    result = await RegisterUser(
        repository, hasher, clock=lambda: NOW, id_factory=lambda: user_id
    ).execute(" Alice ", " ALICE@EXAMPLE.COM ", PASSWORD)
    stored = await repository.get_by_id(user_id)
    assert stored is not None
    assert stored.password_hash != PASSWORD
    assert await hasher.verify(PASSWORD, stored.password_hash)
    assert not await hasher.verify(PASSWORD.strip(), stored.password_hash)
    assert asdict(result) == {
        "id": user_id,
        "name": "Alice",
        "email": "alice@example.com",
        "created_at": NOW,
    }
    assert PASSWORD not in repr(result)
    assert stored.password_hash not in repr(result)
    assert PASSWORD not in caplog.text
    assert stored.password_hash not in caplog.text


@pytest.mark.parametrize(
    ("name", "email", "password"),
    [
        ("", "alice@example.com", PASSWORD),
        ("a" * 101, "alice@example.com", PASSWORD),
        ("Alice", "invalid", PASSWORD),
        ("Alice", "alice@example.com", "short"),
        ("Alice", "alice@example.com", "a" * 129),
        (None, "alice@example.com", PASSWORD),
    ],
)
async def test_invalid_registration_performs_no_dependency_operations(name, email, password):
    repository, hasher = AsyncMock(), AsyncMock()
    with pytest.raises(InvalidUserData):
        await RegisterUser(repository, hasher).execute(name, email, password)
    repository.get_by_email.assert_not_awaited()
    repository.add.assert_not_awaited()
    hasher.hash.assert_not_awaited()


async def test_normalized_duplicate_is_rejected_before_hashing(dependencies):
    repository, hasher = dependencies
    await RegisterUser(repository, hasher).execute("Alice", "alice@example.com", PASSWORD)
    failing_hasher = AsyncMock()
    with pytest.raises(EmailAlreadyRegistered):
        await RegisterUser(repository, failing_hasher).execute(
            "Another", " ALICE@EXAMPLE.COM ", PASSWORD
        )
    failing_hasher.hash.assert_not_awaited()
    assert (await repository.get_by_email("alice@example.com")).name == "Alice"


async def test_duplicate_created_between_lookup_and_add_keeps_one_account(dependencies):
    repository, hasher = dependencies
    existing = User(
        id=uuid4(),
        name="First",
        email="alice@example.com",
        password_hash=await hasher.hash(PASSWORD),
        created_at=NOW,
    )
    original_add = repository.add

    async def racing_add(user):
        await original_add(existing)
        await original_add(user)

    repository.add = racing_add
    with pytest.raises(EmailAlreadyRegistered):
        await RegisterUser(repository, hasher).execute("Second", existing.email, PASSWORD)
    assert await repository.get_by_email(existing.email) == existing


@pytest.mark.parametrize("failure", ["read", "hash", "write"])
async def test_dependency_failure_creates_no_user(dependencies, failure, caplog):
    repository, hasher = dependencies
    repository.fail_reads = failure == "read"
    repository.fail_writes = failure == "write"
    hasher.fail_hashing = failure == "hash"
    with pytest.raises(DependencyUnavailable) as error:
        await RegisterUser(repository, hasher).execute("Alice", "alice@example.com", PASSWORD)
    repository.fail_reads = False
    assert await repository.get_by_email("alice@example.com") is None
    assert PASSWORD not in str(error.value)
    assert PASSWORD not in caplog.text
