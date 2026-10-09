from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.errors import DependencyUnavailable, NotAuthenticated
from app.application.use_cases.authenticate_user import AuthenticateUser
from app.domain.entities import User
from tests.unit.application.fakes import FakeTokenService, FakeUserRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def dependencies():
    repository = FakeUserRepository()
    tokens = FakeTokenService(clock=lambda: NOW)
    user = User(
        id=uuid4(),
        name="Alice",
        email="alice@example.com",
        password_hash="private-hash",
        created_at=NOW,
    )
    await repository.add(user)
    token = await tokens.issue(user.id)
    return repository, tokens, user, token, AuthenticateUser(repository, tokens)


async def test_valid_token_resolves_existing_user(dependencies, caplog):
    _, _, user, token, authenticate = dependencies
    assert await authenticate.execute(token.access_token) == user
    assert token.access_token not in caplog.text
    assert user.password_hash not in caplog.text


@pytest.mark.parametrize("token", ["", None, 123])
async def test_missing_or_invalid_token_shape_performs_no_dependency_io(token):
    repository, tokens = AsyncMock(), AsyncMock()
    with pytest.raises(NotAuthenticated):
        await AuthenticateUser(repository, tokens).execute(token)
    tokens.verify.assert_not_awaited()
    repository.get_by_id.assert_not_awaited()


async def test_invalid_token_does_not_look_up_user(dependencies):
    _, tokens, _, _, _ = dependencies
    repository = AsyncMock()
    with pytest.raises(NotAuthenticated):
        await AuthenticateUser(repository, tokens).execute("invalid-token")
    repository.get_by_id.assert_not_awaited()


async def test_expired_token_does_not_look_up_user(dependencies):
    _, tokens, _, token, _ = dependencies
    tokens.clock = lambda: NOW + timedelta(seconds=3600)
    repository = AsyncMock()
    with pytest.raises(NotAuthenticated):
        await AuthenticateUser(repository, tokens).execute(token.access_token)
    repository.get_by_id.assert_not_awaited()


async def test_token_subject_must_belong_to_existing_user(dependencies):
    _, tokens, _, _, authenticate = dependencies
    unknown = await tokens.issue(uuid4())
    with pytest.raises(NotAuthenticated):
        await authenticate.execute(unknown.access_token)


@pytest.mark.parametrize("subject", ["invalid-uuid", str(uuid4()), None, 123])
async def test_non_uuid_subject_is_rejected_before_lookup(subject):
    repository, tokens = AsyncMock(), AsyncMock()
    tokens.verify.return_value = subject
    with pytest.raises(NotAuthenticated):
        await AuthenticateUser(repository, tokens).execute("some-token")
    repository.get_by_id.assert_not_awaited()


@pytest.mark.parametrize("failure", ["verify", "read"])
async def test_dependency_failure_is_not_invalid_authentication(dependencies, failure):
    repository, tokens, _, token, authenticate = dependencies
    tokens.fail_verify = failure == "verify"
    repository.fail_reads = failure == "read"
    with pytest.raises(DependencyUnavailable):
        await authenticate.execute(token.access_token)
