from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.application.errors import DependencyUnavailable, InvalidCredentials
from app.application.use_cases.login_user import LoginUser
from app.application.use_cases.register_user import RegisterUser
from app.domain.errors import InvalidUserData
from tests.unit.application.fakes import FakePasswordHasher, FakeTokenService, FakeUserRepository

PASSWORD = "  secure password  "
NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def dependencies():
    repository, hasher = FakeUserRepository(), FakePasswordHasher()
    tokens = FakeTokenService(clock=lambda: NOW)
    user = await RegisterUser(repository, hasher).execute("Alice", "alice@example.com", PASSWORD)
    dummy_hash = await hasher.hash("dummy-password")
    login = LoginUser(repository, hasher, tokens, dummy_password_hash=dummy_hash)
    return repository, hasher, tokens, user, dummy_hash, login


async def test_success_returns_token_for_normalized_email(dependencies, caplog):
    _, _, tokens, user, _, login = dependencies
    result = await login.execute(" ALICE@EXAMPLE.COM ", PASSWORD)
    assert result.expires_in == 3600
    assert await tokens.verify(result.access_token) == user.id
    assert PASSWORD not in repr(result)
    assert PASSWORD not in caplog.text
    assert result.access_token not in caplog.text


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("alice@example.com", "wrong-password"),
        ("unknown@example.com", PASSWORD),
        ("alice@example.com", PASSWORD.strip()),
    ],
)
async def test_invalid_credentials_never_issue_token(dependencies, email, password):
    repository, hasher, _, _, dummy_hash, _ = dependencies
    tokens = AsyncMock()
    with pytest.raises(InvalidCredentials) as error:
        await LoginUser(repository, hasher, tokens, dummy_password_hash=dummy_hash).execute(
            email, password
        )
    assert str(error.value) == "Invalid credentials"
    assert PASSWORD not in str(error.value)
    tokens.issue.assert_not_awaited()


async def test_unknown_user_verifies_dummy_hash_and_rejects_even_if_it_matches(dependencies):
    repository, _, _, _, dummy_hash, _ = dependencies
    hasher, tokens = AsyncMock(), AsyncMock()
    hasher.verify.return_value = True
    with pytest.raises(InvalidCredentials):
        await LoginUser(repository, hasher, tokens, dummy_password_hash=dummy_hash).execute(
            "unknown@example.com", "dummy-password"
        )
    hasher.verify.assert_awaited_once_with("dummy-password", dummy_hash)
    tokens.issue.assert_not_awaited()


async def test_known_user_verifies_stored_hash_once(dependencies):
    repository, hasher, tokens, user, dummy_hash, _ = dependencies
    stored = await repository.get_by_id(user.id)
    spy = AsyncMock(wraps=hasher)
    await LoginUser(repository, spy, tokens, dummy_password_hash=dummy_hash).execute(
        user.email, PASSWORD
    )
    spy.verify.assert_awaited_once_with(PASSWORD, stored.password_hash)


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("invalid", PASSWORD),
        ("alice@example.com", "short"),
        ("alice@example.com", "a" * 129),
        (None, PASSWORD),
    ],
)
async def test_invalid_input_performs_no_io(email, password):
    repository, hasher, tokens = AsyncMock(), AsyncMock(), AsyncMock()
    with pytest.raises(InvalidUserData):
        await LoginUser(repository, hasher, tokens, dummy_password_hash="dummy-hash").execute(
            email, password
        )
    repository.get_by_email.assert_not_awaited()
    hasher.verify.assert_not_awaited()
    tokens.issue.assert_not_awaited()


@pytest.mark.parametrize("failure", ["read", "verify", "token"])
async def test_dependency_failure_is_not_misreported_as_bad_credentials(dependencies, failure):
    repository, hasher, tokens, _, _, login = dependencies
    repository.fail_reads = failure == "read"
    hasher.fail_verification = failure == "verify"
    tokens.fail_issue = failure == "token"
    with pytest.raises(DependencyUnavailable):
        await login.execute("alice@example.com", PASSWORD)


async def test_dummy_verification_failure_remains_dependency_failure(dependencies):
    _, hasher, _, _, _, login = dependencies
    hasher.fail_verification = True
    with pytest.raises(DependencyUnavailable):
        await login.execute("unknown@example.com", PASSWORD)
