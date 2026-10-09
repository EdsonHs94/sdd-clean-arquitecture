"""HTTP acceptance gaps: real JWT variants on every protected route and JSON boundaries."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import jwt
import pytest

from app.domain.entities import User
from app.infrastructure.security.tokens import JwtTokenService
from app.presentation.dependencies import get_token_service
from tests.unit.application.fakes import make_file

NOW = datetime(2026, 1, 1, tzinfo=UTC)
SECRET = "acceptance-dummy-signing-secret-at-least-32-bytes"
ISSUER = "user-architecture-model"
AUDIENCE = "user-architecture-model-api"
ROUTES = [
    ("GET", "/me"),
    ("POST", "/files"),
    ("GET", "/files"),
    ("GET", "/files/owned"),
    ("DELETE", "/files/owned"),
]
VARIANTS = [
    "missing",
    "basic",
    "empty_bearer",
    "malformed",
    "tampered",
    "wrong_signature",
    "expired",
    "expiry_instant",
    "wrong_issuer",
    "wrong_audience",
    "audience_array",
    "HS384",
    "HS512",
    "none",
    "unknown_user",
    "invalid_sub",
    "integer_sub",
    "null_sub",
    "string_exp",
    "float_exp",
    "bool_exp",
    "string_iat",
    "float_iat",
    "bool_iat",
    "future_iat",
    "null_exp",
    "null_iat",
    "null_iss",
    "integer_iss",
    "null_aud",
    "integer_aud",
    "modified_payload",
    "missing_sub",
    "missing_exp",
    "missing_iat",
    "missing_iss",
    "missing_aud",
]


class FrozenDateTime(datetime):
    current = NOW

    @classmethod
    def now(cls, tz=None):
        return cls.current.astimezone(tz) if tz is not None else cls.current.replace(tzinfo=None)


@pytest.fixture
async def jwt_context(api, api_context, file_context, monkeypatch):
    user = User(uuid4(), "Alice", "alice@example.com", "private-hash", NOW)
    await api_context[1].add(user)
    service = JwtTokenService(SECRET, clock=lambda: NOW)
    api_context[0].dependency_overrides[get_token_service] = lambda: service
    monkeypatch.setattr(jwt.api_jwt, "datetime", FrozenDateTime)
    file = make_file(user.id)
    await file_context[0].add(file)
    await file_context[1].upload(file.storage_key, b"abc", file.content_type)
    file_context[1].calls.clear()
    return user, file, service


def header_for(user_id, variant):
    claims = {
        "sub": str(user_id),
        "iat": int(NOW.timestamp()),
        "exp": int(NOW.timestamp()) + 3600,
        "iss": ISSUER,
        "aud": AUDIENCE,
    }
    if variant == "missing":
        return {}
    if variant == "basic":
        return {"Authorization": "Basic private-credential"}
    if variant == "empty_bearer":
        return {"Authorization": "Bearer"}
    if variant == "malformed":
        return {"Authorization": "Bearer a.b.c"}
    changes = {
        "expired": {"exp": int(NOW.timestamp()) - 1},
        "expiry_instant": {"exp": int(NOW.timestamp())},
        "wrong_issuer": {"iss": "wrong"},
        "wrong_audience": {"aud": "wrong"},
        "audience_array": {"aud": [AUDIENCE]},
        "unknown_user": {"sub": str(uuid4())},
        "invalid_sub": {"sub": "not-a-uuid"},
        "integer_sub": {"sub": 123},
        "null_sub": {"sub": None},
        "string_exp": {"exp": str(int(NOW.timestamp()) + 3600)},
        "float_exp": {"exp": float(NOW.timestamp()) + 3600},
        "bool_exp": {"exp": True},
        "string_iat": {"iat": str(int(NOW.timestamp()))},
        "float_iat": {"iat": float(NOW.timestamp())},
        "bool_iat": {"iat": True},
        "future_iat": {"iat": int(NOW.timestamp()) + 1},
        "null_exp": {"exp": None},
        "null_iat": {"iat": None},
        "null_iss": {"iss": None},
        "integer_iss": {"iss": 123},
        "null_aud": {"aud": None},
        "integer_aud": {"aud": 123},
    }
    claims.update(changes.get(variant, {}))
    if variant.startswith("missing_"):
        del claims[variant.removeprefix("missing_")]
    algorithm = variant if variant in ("HS384", "HS512", "none") else "HS256"
    if algorithm == "none":
        key = None
    elif variant == "wrong_signature":
        key = "wrong-secret-at-least-32-bytes-long"
    else:
        key = SECRET * 2 if algorithm in ("HS384", "HS512") else SECRET
    # Sign raw JSON to exercise invalid claims that the high-level encoder refuses.
    token = jwt.api_jws.encode(json.dumps(claims).encode(), key, algorithm=algorithm)
    if variant == "modified_payload":
        modified = jwt.encode({**claims, "sub": str(uuid4())}, SECRET, algorithm="HS256")
        token = ".".join(modified.split(".")[:2] + [token.split(".")[2]])
    if variant == "tampered":
        head, payload, signature = token.split(".")
        signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        token = ".".join((head, payload, signature))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(("method", "path"), ROUTES)
@pytest.mark.parametrize("variant", VARIANTS)
async def test_all_token_variants_on_every_protected_route(
    api, file_context, jwt_context, caplog, method, path, variant
):
    user, file, _ = jwt_context
    repo, storage = file_context
    for operation in ("add", "list_by_owner", "get_owned", "delete_owned"):
        setattr(repo, operation, AsyncMock(wraps=getattr(repo, operation)))
    headers = header_for(user.id, variant)
    kwargs = {"files": {"file": ("a", b"abc")}} if method == "POST" else {}
    response = await api.request(
        method, path.replace("owned", str(file.id)), headers=headers, **kwargs
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"
    for operation in ("add", "list_by_owner", "get_owned", "delete_owned"):
        getattr(repo, operation).assert_not_awaited()
    assert storage.calls == []
    for sensitive in (
        SECRET,
        user.password_hash,
        file.storage_key,
        headers.get("Authorization", ""),
    ):
        if sensitive:
            assert sensitive not in response.text
            assert sensitive not in caplog.text


@pytest.mark.parametrize(("method", "path"), ROUTES)
@pytest.mark.parametrize("elapsed", [0, 3599])
async def test_real_valid_jwt_is_accepted_on_each_route(
    api, jwt_context, monkeypatch, method, path, elapsed
):
    user, file, service = jwt_context
    token = await service.issue(user.id)
    monkeypatch.setattr(FrozenDateTime, "current", NOW + timedelta(seconds=elapsed))
    kwargs = {"files": {"file": ("a", b"abc")}} if method == "POST" else {}
    response = await api.request(
        method,
        path.replace("owned", str(file.id)),
        headers={"Authorization": f"bearer {token.access_token}"},
        **kwargs,
    )
    assert response.status_code == (201 if method == "POST" else 204 if method == "DELETE" else 200)


@pytest.mark.parametrize("body", [None, [], "private-password", 123, True])
@pytest.mark.parametrize("path", ["/users", "/auth/login"])
async def test_non_object_json_is_422_and_does_not_echo_input(api, api_context, path, body):
    # json=None in httpx means no body; other cases exercise actual JSON types.
    response = await api.post(path, json=body)
    assert response.status_code == 422
    assert "private-password" not in response.text
    assert await api_context[1].get_by_email("alice@example.com") is None
    assert all(set(error) == {"loc", "msg", "type"} for error in response.json()["detail"])


@pytest.mark.parametrize(("name", "password"), [("a", "x" * 8), ("x" * 100, "x" * 128)])
async def test_registration_accepts_exact_name_and_password_boundaries(api, name, password):
    response = await api.post(
        "/users",
        json={
            "name": name,
            "email": "boundary@example.com",
            "password": password,
        },
    )
    assert response.status_code == 201
    login = await api.post(
        "/auth/login", json={"email": "boundary@example.com", "password": password}
    )
    assert login.status_code == 200


@pytest.mark.parametrize(("method", "path"), ROUTES)
async def test_authentication_outage_precedes_file_operations(
    api, api_context, file_context, jwt_context, method, path
):
    user, file, service = jwt_context
    token = await service.issue(user.id)
    api_context[1].fail_reads = True
    file_context[0].get_owned = AsyncMock(wraps=file_context[0].get_owned)
    file_context[0].list_by_owner = AsyncMock(wraps=file_context[0].list_by_owner)
    response = await api.request(
        method,
        path.replace("owned", str(file.id)),
        headers={"Authorization": f"Bearer {token.access_token}"},
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}
    file_context[0].get_owned.assert_not_awaited()
    file_context[0].list_by_owner.assert_not_awaited()
    assert file_context[1].calls == []


@pytest.mark.parametrize("length", [254, 255])
async def test_email_length_boundary_at_http_boundary(api, api_context, length):
    email = "a" * 64 + "@" + "b" * 63 + "." + "c" * 63 + "." + "d" * (length - 193)
    assert len(email) == length
    response = await api.post(
        "/users",
        json={
            "name": "Alice",
            "email": email,
            "password": "secure-password",
        },
    )
    assert response.status_code == (201 if length == 254 else 422)
    stored = await api_context[1].get_by_email(email)
    assert (stored is not None) is (length == 254)


async def test_login_requires_email(api):
    response = await api.post("/auth/login", json={"password": "private-password"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "email"]
    assert "private-password" not in response.text
