from dataclasses import is_dataclass
from datetime import UTC, datetime, timedelta
from typing import get_type_hints
from uuid import UUID, uuid4

import pytest

from app.application.dto import TokenResult
from app.application.errors import DependencyUnavailable, NotAuthenticated
from app.application.ports import TokenService
from tests.unit.application.fakes import FakeTokenService

NOW = datetime(2026, 1, 1, tzinfo=UTC)


async def issue_token(service: TokenService, user_id: UUID) -> TokenResult:
    return await service.issue(user_id)


async def test_issue_returns_plain_token_result_and_verified_subject():
    service = FakeTokenService(clock=lambda: NOW)
    user_id = uuid4()
    result = await issue_token(service, user_id)
    assert isinstance(result, TokenResult)
    assert is_dataclass(result)
    assert get_type_hints(TokenResult) == {"access_token": str, "expires_in": int}
    assert isinstance(result.access_token, str)
    assert result.access_token
    assert result.expires_in == 3600
    assert await service.verify(result.access_token) == user_id


async def test_two_users_tokens_resolve_to_their_own_subjects():
    service = FakeTokenService(clock=lambda: NOW)
    first, second = uuid4(), uuid4()
    first_token, second_token = await service.issue(first), await service.issue(second)
    assert first_token.access_token != second_token.access_token
    assert await service.verify(first_token.access_token) == first
    assert await service.verify(second_token.access_token) == second


@pytest.mark.parametrize("token", ["", "unknown-token", "Bearer invalid", "tampered-token"])
async def test_unknown_or_malformed_token_is_not_authenticated(token, caplog):
    service = FakeTokenService(clock=lambda: NOW)
    with pytest.raises(NotAuthenticated) as error:
        await service.verify(token)
    assert str(error.value) == "Not authenticated"
    assert "unknown-token" not in caplog.text


@pytest.mark.parametrize("elapsed", [3599, 3600, 3601])
async def test_expiration_is_deterministic_and_exclusive(elapsed):
    service = FakeTokenService(clock=lambda: NOW)
    user_id = uuid4()
    result = await service.issue(user_id)
    service.clock = lambda: NOW + timedelta(seconds=elapsed)
    if elapsed < result.expires_in:
        assert await service.verify(result.access_token) == user_id
    else:
        with pytest.raises(NotAuthenticated):
            await service.verify(result.access_token)


@pytest.mark.parametrize("operation", ["issue", "verify"])
async def test_dependency_failure_is_distinct_from_invalid_token(operation):
    service = FakeTokenService(clock=lambda: NOW)
    if operation == "issue":
        service.fail_issue = True
        call = service.issue(uuid4())
    else:
        service.fail_verify = True
        call = service.verify("sensitive-token")
    with pytest.raises(DependencyUnavailable) as error:
        await call
    assert not isinstance(error.value, NotAuthenticated)
    assert "sensitive-token" not in str(error.value)


async def test_token_and_subject_do_not_appear_in_representations_or_logs(caplog):
    service = FakeTokenService(clock=lambda: NOW)
    user_id = uuid4()
    result = await service.issue(user_id)
    assert result.access_token not in repr(result)
    assert result.access_token not in repr(service)
    assert str(user_id) not in repr(service)
    assert result.access_token not in caplog.text
