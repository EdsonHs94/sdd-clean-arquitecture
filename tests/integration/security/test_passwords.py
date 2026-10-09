import threading
from unittest.mock import AsyncMock

import pytest
from argon2.exceptions import HashingError, InvalidHashError, VerificationError

from app.application.errors import DependencyUnavailable, InvalidCredentials
from app.application.use_cases.login_user import LoginUser
from app.infrastructure.security.passwords import Argon2PasswordHasher
from tests.unit.application.fakes import FakeUserRepository


@pytest.fixture
def hasher():
    return Argon2PasswordHasher()


@pytest.mark.parametrize("password", ["secure-password", "a" * 128, "  pass  ", "contraseña"])
async def test_real_argon2id_roundtrip_and_mismatch(hasher, password, caplog):
    result = await hasher.hash(password)
    assert result.startswith("$argon2id$")
    assert result != password
    assert password not in result
    assert await hasher.verify(password, result)
    assert not await hasher.verify("wrong-password", result)
    assert password not in caplog.text
    assert result not in caplog.text


async def test_independent_hashes_have_distinct_salts(hasher):
    first, second = await hasher.hash("secure-password"), await hasher.hash("secure-password")
    assert first != second
    assert first.split("$")[4] != second.split("$")[4]
    assert await hasher.verify("secure-password", first)
    assert await hasher.verify("secure-password", second)


async def test_password_whitespace_is_preserved(hasher):
    result = await hasher.hash("  pass  ")
    assert not await hasher.verify("pass", result)


@pytest.mark.parametrize("bad_hash", ["", "plain-password", "$argon2id$broken"])
async def test_malformed_stored_hash_is_a_dependency_failure(hasher, bad_hash, caplog):
    with pytest.raises(DependencyUnavailable) as error:
        await hasher.verify("sensitive-password", bad_hash)
    assert "sensitive-password" not in str(error.value)
    assert "sensitive-password" not in caplog.text
    if bad_hash:
        assert bad_hash not in str(error.value)


@pytest.mark.parametrize(
    ("operation", "exception"),
    [
        ("hash", HashingError),
        ("verify", VerificationError),
        ("verify", InvalidHashError),
    ],
)
async def test_vendor_failures_are_sanitized(hasher, operation, exception, monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise exception("sensitive-password private-hash")

    monkeypatch.setattr(type(hasher._hasher), operation, fail)
    with pytest.raises(DependencyUnavailable) as error:
        if operation == "hash":
            await hasher.hash("sensitive-password")
        else:
            await hasher.verify("sensitive-password", "private-hash")
    assert str(error.value) == "Service unavailable"
    assert error.value.__suppress_context__
    assert "sensitive-password" not in caplog.text
    assert "private-hash" not in caplog.text


async def test_hash_and_verify_execute_outside_the_event_loop_thread(hasher, monkeypatch):
    event_loop_thread = threading.get_ident()
    called_on = []
    real_hash, real_verify = hasher._hasher.hash, hasher._hasher.verify

    def hash_spy(_self, password):
        called_on.append(threading.get_ident())
        return real_hash(password)

    def verify_spy(_self, password_hash, password):
        called_on.append(threading.get_ident())
        return real_verify(password_hash, password)

    monkeypatch.setattr(type(hasher._hasher), "hash", hash_spy)
    monkeypatch.setattr(type(hasher._hasher), "verify", verify_spy)
    result = await hasher.hash("secure-password")
    assert await hasher.verify("secure-password", result)
    assert len(called_on) == 2
    assert all(thread != event_loop_thread for thread in called_on)


async def test_unknown_account_uses_real_dummy_verification(hasher):
    dummy_hash = await hasher.hash("dummy-password")
    spy = AsyncMock(wraps=hasher)
    tokens = AsyncMock()
    login = LoginUser(FakeUserRepository(), spy, tokens, dummy_password_hash=dummy_hash)
    with pytest.raises(InvalidCredentials):
        await login.execute("unknown@example.com", "dummy-password")
    spy.verify.assert_awaited_once_with("dummy-password", dummy_hash)
    tokens.issue.assert_not_awaited()
