import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest

from app.application.errors import DependencyUnavailable, NotAuthenticated
from app.application.use_cases.authenticate_user import AuthenticateUser
from app.application.use_cases.login_user import LoginUser
from app.application.use_cases.register_user import RegisterUser
from app.infrastructure.security.passwords import Argon2PasswordHasher
from app.infrastructure.security.tokens import JwtTokenService
from tests.unit.application.fakes import FakeUserRepository

# Explicit test-only key; production configuration must supply a random secret.
SECRET = "test-only-signing-secret-32-bytes-long"
ISSUER = "user-architecture-model"
AUDIENCE = "user-architecture-model-api"
NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def clock(monkeypatch):
    class ControlledDateTime(datetime):
        current = NOW

        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return cls.current.replace(tzinfo=None)
            return cls.current.astimezone(tz)

    # Only tests override the library clock. Production retains every verification check.
    monkeypatch.setattr(jwt.api_jwt, "datetime", ControlledDateTime)
    return ControlledDateTime


@pytest.fixture
def service(clock):
    return JwtTokenService(SECRET, clock=lambda: clock.current)


@pytest.fixture
def claims():
    issued = int(NOW.timestamp())
    return {
        "sub": str(uuid4()),
        "iat": issued,
        "exp": issued + 3600,
        "iss": ISSUER,
        "aud": AUDIENCE,
    }


def encode(claims, *, secret=SECRET, algorithm="HS256"):
    # Sign raw attacker-controlled JSON, bypassing issuer checks in the encoder.
    # This does not disable any decoder verification in the adapter under test.
    return jwt.api_jws.encode(json.dumps(claims).encode(), secret, algorithm=algorithm)


async def test_issued_token_has_only_required_claims_and_verifiable_subject(service, claims):
    user_id = UUID(claims["sub"])
    result = await service.issue(user_id)
    assert result.expires_in == 3600
    payload = jwt.decode(
        result.access_token,
        SECRET,
        algorithms=["HS256"],
        issuer=ISSUER,
        audience=AUDIENCE,
        options={"require": ["sub", "exp", "iat", "iss", "aud"]},
    )
    assert payload == claims
    assert jwt.get_unverified_header(result.access_token)["alg"] == "HS256"
    assert await service.verify(result.access_token) == user_id
    assert result.access_token not in repr(result)
    assert SECRET not in repr(service)


@pytest.mark.parametrize("elapsed", [3599, 3600, 3601])
async def test_token_expiry_is_exclusive_without_leeway(service, clock, elapsed):
    user_id = uuid4()
    token = await service.issue(user_id)
    clock.current = NOW + timedelta(seconds=elapsed)
    if elapsed < 3600:
        assert await service.verify(token.access_token) == user_id
    else:
        with pytest.raises(NotAuthenticated):
            await service.verify(token.access_token)


async def test_wrong_signature_key_is_rejected(service, claims):
    with pytest.raises(NotAuthenticated):
        await service.verify(encode(claims, secret="another-test-only-key-at-least-32-bytes"))


async def test_modified_payload_is_rejected(service, claims):
    original = encode(claims)
    modified = encode({**claims, "sub": str(uuid4())})
    tampered = ".".join(modified.split(".")[:2] + [original.split(".")[2]])
    with pytest.raises(NotAuthenticated):
        await service.verify(tampered)


@pytest.mark.parametrize("algorithm", ["HS384", "HS512", "none"])
async def test_unsupported_algorithm_is_rejected(service, claims, algorithm):
    token = encode(claims, secret="" if algorithm == "none" else SECRET * 2, algorithm=algorithm)
    with pytest.raises(NotAuthenticated):
        await service.verify(token)


@pytest.mark.parametrize("field", ["sub", "exp", "iat", "iss", "aud"])
async def test_required_claim_cannot_be_missing(service, claims, field):
    del claims[field]
    with pytest.raises(NotAuthenticated):
        await service.verify(encode(claims))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("exp", str(int(NOW.timestamp()) + 3600)),
        ("exp", float(NOW.timestamp()) + 3600),
        ("exp", True),
        ("exp", None),
        ("iat", str(int(NOW.timestamp()))),
        ("iat", float(NOW.timestamp())),
        ("iat", True),
        ("iat", None),
        ("iat", int(NOW.timestamp()) + 1),
        ("sub", "invalid-uuid"),
        ("sub", 123),
        ("sub", None),
        ("iss", "wrong-issuer"),
        ("iss", None),
        ("iss", 123),
        ("aud", "wrong-audience"),
        ("aud", [AUDIENCE]),
        ("aud", None),
        ("aud", 123),
    ],
)
async def test_invalid_claim_types_and_values_are_rejected(service, claims, field, value):
    claims[field] = value
    with pytest.raises(NotAuthenticated):
        await service.verify(encode(claims))


@pytest.mark.parametrize("token", ["", "malformed", "a.b.c", None, 123])
async def test_invalid_token_shape_is_rejected(service, token):
    with pytest.raises(NotAuthenticated):
        await service.verify(token)


async def test_configured_issuer_and_audience_are_used(clock, claims):
    service = JwtTokenService(
        SECRET, issuer="custom-issuer", audience="custom-audience", clock=lambda: clock.current
    )
    user_id = uuid4()
    issued = await service.issue(user_id)
    assert await service.verify(issued.access_token) == user_id
    with pytest.raises(NotAuthenticated):
        await service.verify(encode(claims))


@pytest.mark.parametrize("secret", ["", "short", "a" * 31, None])
def test_weak_or_missing_signing_secret_is_rejected_without_echoing_value(secret):
    with pytest.raises(ValueError) as error:
        JwtTokenService(secret)
    if isinstance(secret, str) and secret:
        assert secret not in str(error.value)


@pytest.mark.parametrize(("field", "value"), [("issuer", ""), ("audience", "")])
def test_empty_token_identity_configuration_is_rejected(field, value):
    with pytest.raises(ValueError):
        JwtTokenService(SECRET, **{field: value})


@pytest.mark.parametrize("operation", ["issue", "verify"])
async def test_crypto_dependency_failure_is_sanitized(service, monkeypatch, operation, caplog):
    def fail(*args, **kwargs):
        raise jwt.InvalidKeyError("private-signing-secret sensitive-token")

    monkeypatch.setattr(jwt, "encode" if operation == "issue" else "decode", fail)
    with pytest.raises(DependencyUnavailable) as error:
        if operation == "issue":
            await service.issue(uuid4())
        else:
            await service.verify("sensitive-token")
    assert str(error.value) == "Service unavailable"
    assert error.value.__suppress_context__
    assert "private-signing-secret" not in caplog.text
    assert "sensitive-token" not in caplog.text


async def test_rejected_token_is_not_logged_or_echoed(service, claims, caplog):
    claims["aud"] = "wrong-audience"
    token = encode(claims)
    with pytest.raises(NotAuthenticated) as error:
        await service.verify(token)
    assert token not in str(error.value)
    assert token not in caplog.text
    assert SECRET not in caplog.text
    assert error.value.__suppress_context__


async def test_real_hash_and_token_adapters_work_through_account_use_cases(service):
    repository = FakeUserRepository()
    hasher = Argon2PasswordHasher()
    user = await RegisterUser(repository, hasher).execute(
        "Alice", "alice@example.com", "secure-password"
    )
    dummy_hash = await hasher.hash("dummy-password")
    result = await LoginUser(repository, hasher, service, dummy_password_hash=dummy_hash).execute(
        " ALICE@EXAMPLE.COM ", "secure-password"
    )
    authenticated = await AuthenticateUser(repository, service).execute(result.access_token)
    assert authenticated.id == user.id
    token_for_absent_user = await service.issue(uuid4())
    with pytest.raises(NotAuthenticated):
        await AuthenticateUser(repository, service).execute(token_for_absent_user.access_token)
