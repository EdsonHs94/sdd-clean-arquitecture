from datetime import UTC, datetime
from uuid import UUID

import pytest

REGISTRATION = {
    "name": " Alice ",
    "email": " ALICE@EXAMPLE.COM ",
    "password": "  secure password  ",
}


async def test_registration_returns_normalized_safe_profile_and_hashed_password(api, api_context):
    response = await api.post("/users", json=REGISTRATION)
    assert response.status_code == 201
    profile = response.json()
    assert set(profile) == {"id", "name", "email", "created_at"}
    assert UUID(profile["id"])
    assert profile["name"] == "Alice"
    assert profile["email"] == "alice@example.com"
    assert datetime.fromisoformat(
        profile["created_at"].replace("Z", "+00:00")
    ).utcoffset() == UTC.utcoffset(None)
    _, repository, hasher, _ = api_context
    stored = await repository.get_by_email(profile["email"])
    assert await hasher.verify(REGISTRATION["password"], stored.password_hash)
    assert stored.password_hash not in response.text
    assert REGISTRATION["password"] not in response.text


async def test_duplicate_normalized_email_returns_409(api, api_context):
    assert (await api.post("/users", json=REGISTRATION)).status_code == 201
    response = await api.post("/users", json={**REGISTRATION, "email": "alice@example.com"})
    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
    assert (await api_context[1].get_by_email("alice@example.com")).name == "Alice"


@pytest.mark.parametrize(
    "changes",
    [
        {"name": ""},
        {"name": "a" * 101},
        {"email": "invalid"},
        {"password": "short"},
        {"password": "a" * 129},
        {"password": 123},
        {"email": None},
        {"name": 123},
        {"extra": "sensitive-extra-value"},
        {"password": {"private": "sensitive-password"}},
    ],
)
async def test_invalid_registration_returns_safe_422_without_persistence(api, api_context, changes):
    response = await api.post("/users", json={**REGISTRATION, **changes})
    assert response.status_code == 422
    assert "sensitive-password" not in response.text
    assert "sensitive-extra-value" not in response.text
    assert await api_context[1].get_by_email("alice@example.com") is None
    for error in response.json()["detail"]:
        assert set(error) == {"loc", "msg", "type"}


@pytest.mark.parametrize("field", ["name", "email", "password"])
async def test_registration_requires_all_fields(api, field):
    response = await api.post(
        "/users", json={key: value for key, value in REGISTRATION.items() if key != field}
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]


async def test_login_issues_bearer_token_for_normalized_credentials(api, api_context):
    registration = await api.post("/users", json=REGISTRATION)
    assert registration.status_code == 201
    response = await api.post(
        "/auth/login", json={"email": " Alice@Example.Com ", "password": REGISTRATION["password"]}
    )
    assert response.status_code == 200
    result = response.json()
    assert set(result) == {"access_token", "token_type", "expires_in"}
    assert result["token_type"] == "bearer"
    assert result["expires_in"] == 3600
    assert str(await api_context[3].verify(result["access_token"])) == registration.json()["id"]
    assert REGISTRATION["password"] not in response.text


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("alice@example.com", "wrong-password"),
        ("unknown@example.com", REGISTRATION["password"]),
    ],
)
async def test_invalid_credentials_return_identical_401_with_challenge(api, email, password):
    assert (await api.post("/users", json=REGISTRATION)).status_code == 201
    response = await api.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "body",
    [
        {"email": "invalid", "password": "secure-password"},
        {"email": "alice@example.com", "password": "short"},
        {"email": "alice@example.com", "password": 123},
        {"email": "alice@example.com"},
        {
            "email": "alice@example.com",
            "password": "secure-password",
            "name": "sensitive-extra-value",
        },
    ],
)
async def test_invalid_login_input_is_422_and_sanitized(api, body):
    response = await api.post("/auth/login", json=body)
    assert response.status_code == 422
    assert "sensitive-extra-value" not in response.text
    assert "secure-password" not in response.text


@pytest.mark.parametrize("failure", ["read", "hash", "write"])
async def test_registration_outages_are_sanitized_503(api, api_context, failure):
    _, repository, hasher, _ = api_context
    repository.fail_reads = failure == "read"
    repository.fail_writes = failure == "write"
    hasher.fail_hashing = failure == "hash"
    response = await api.post("/users", json=REGISTRATION)
    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}


@pytest.mark.parametrize("failure", ["read", "verify", "token"])
async def test_login_outages_are_sanitized_503(api, api_context, failure):
    assert (await api.post("/users", json=REGISTRATION)).status_code == 201
    _, repository, hasher, tokens = api_context
    repository.fail_reads = failure == "read"
    hasher.fail_verification = failure == "verify"
    tokens.fail_issue = failure == "token"
    response = await api.post(
        "/auth/login", json={"email": "alice@example.com", "password": REGISTRATION["password"]}
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}
