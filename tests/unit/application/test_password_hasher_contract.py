import pytest

from app.application.errors import DependencyUnavailable
from app.application.ports import PasswordHasher
from tests.unit.application.fakes import FakePasswordHasher


async def hash_password(hasher: PasswordHasher, password: str) -> str:
    return await hasher.hash(password)


@pytest.mark.parametrize("password", ["password", "  pass  ", "a" * 128, "contraseña"])
async def test_fake_hash_roundtrip_is_deterministic_and_not_plaintext(password):
    hasher = FakePasswordHasher()
    result = await hash_password(hasher, password)
    assert result != password
    assert password not in result
    assert result == await hasher.hash(password)
    assert await hasher.verify(password, result) is True


async def test_wrong_password_and_changed_whitespace_do_not_match():
    hasher = FakePasswordHasher()
    result = await hasher.hash("  pass  ")
    assert await hasher.verify("pass", result) is False
    assert await hasher.verify("wrong-password", result) is False


async def test_unknown_hash_does_not_match():
    assert await FakePasswordHasher().verify("password", "unknown-hash") is False


@pytest.mark.parametrize("operation", ["hash", "verify"])
async def test_dependency_failure_does_not_disclose_password(operation, caplog):
    password = "sensitive-password"
    hasher = FakePasswordHasher()
    hasher.fail_hashing = operation == "hash"
    hasher.fail_verification = operation == "verify"
    with pytest.raises(DependencyUnavailable) as error:
        if operation == "hash":
            await hasher.hash(password)
        else:
            await hasher.verify(password, "private-hash")
    assert password not in str(error.value)
    assert "private-hash" not in str(error.value)
    assert password not in caplog.text


async def test_fake_does_not_retain_raw_credentials_in_representation(caplog):
    hasher = FakePasswordHasher()
    await hasher.hash("sensitive-password")
    assert "sensitive-password" not in repr(hasher)
    assert "sensitive-password" not in caplog.text
