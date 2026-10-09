from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest


async def create_account(api, email="alice@example.com", name="Alice"):
    profile = await api.post(
        "/users", json={"name": name, "email": email, "password": "secure-password"}
    )
    assert profile.status_code == 201
    token = await api.post("/auth/login", json={"email": email, "password": "secure-password"})
    assert token.status_code == 200
    return profile.json(), token.json()["access_token"]


async def test_me_returns_only_authenticated_profile(api):
    alice, alice_token = await create_account(api)
    bob, bob_token = await create_account(api, "bob@example.com", "Bob")
    alice_response = await api.get(
        "/me", headers={"Authorization": f"Bearer {alice_token}"}, params={"user_id": bob["id"]}
    )
    bob_response = await api.get("/me", headers={"Authorization": f"Bearer {bob_token}"})
    assert alice_response.status_code == bob_response.status_code == 200
    assert alice_response.json() == alice
    assert bob_response.json() == bob
    assert set(alice_response.json()) == {"id", "name", "email", "created_at"}
    assert "password" not in alice_response.text
    assert "fake-sha256" not in alice_response.text


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer", "Bearer malformed-token"])
async def test_missing_or_malformed_token_returns_safe_challenge(api, header):
    response = await api.get("/me", headers={"Authorization": header} if header else {})
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"


async def test_expired_token_is_401(api, api_context):
    profile, _ = await create_account(api)
    tokens = api_context[3]
    now = datetime(2026, 1, 1, tzinfo=UTC)
    tokens.clock = lambda: now
    issued = await tokens.issue(UUID(profile["id"]))
    tokens.clock = lambda: now + timedelta(seconds=3600)
    response = await api.get("/me", headers={"Authorization": f"Bearer {issued.access_token}"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"


async def test_unknown_user_token_is_401(api, api_context):
    issued = await api_context[3].issue(uuid4())
    response = await api.get("/me", headers={"Authorization": f"Bearer {issued.access_token}"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("failure", ["read", "verify"])
async def test_authentication_outage_is_503(api, api_context, failure):
    _, token = await create_account(api)
    api_context[1].fail_reads = failure == "read"
    api_context[3].fail_verify = failure == "verify"
    response = await api.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}


async def test_me_reuses_resolved_user_without_a_second_lookup(api, api_context, monkeypatch):
    profile, token = await create_account(api)
    repository = api_context[1]
    lookup = AsyncMock(wraps=repository.get_by_id)
    monkeypatch.setattr(repository, "get_by_id", lookup)
    response = await api.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    lookup.assert_awaited_once_with(UUID(profile["id"]))


async def test_missing_authentication_does_not_query_unavailable_repository(api, api_context):
    api_context[1].fail_reads = True
    response = await api.get("/me")
    assert response.status_code == 401
