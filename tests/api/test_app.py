from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from pydantic import BaseModel, ConfigDict

from app.application.errors import (
    DependencyUnavailable,
    EmailAlreadyRegistered,
    InvalidCredentials,
    NotAuthenticated,
)
from app.bootstrap import create_app
from app.domain.entities import User
from app.domain.errors import InvalidUserData
from app.infrastructure.settings import Settings
from app.presentation.dependencies import (
    get_authenticated_user,
    get_token_service,
    get_user_repository,
)
from tests.api.helpers import client_for
from tests.unit.application.fakes import FakeTokenService, FakeUserRepository

CONFIG = {
    "database_url": "postgresql+asyncpg://test:private-db-password@127.0.0.1:1/test",
    "jwt_secret": "test-only-secret-at-least-32-bytes-long",
    "s3_bucket": "test-bucket",
}


def settings(**overrides):
    return Settings(_env_file=None, **{**CONFIG, **overrides})


@pytest.mark.parametrize("field", ["database_url", "jwt_secret", "s3_bucket"])
def test_required_settings_are_missing(monkeypatch, field):
    for name in CONFIG:
        monkeypatch.delenv(name.upper(), raising=False)
    values = {name: value for name, value in CONFIG.items() if name != field}
    with pytest.raises(ValueError):
        Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("jwt_secret", "short"),
        ("database_url", "sqlite:///test.db"),
        ("s3_bucket", ""),
        ("jwt_issuer", ""),
        ("jwt_audience", ""),
    ],
)
def test_invalid_settings_fail_without_echoing_secrets(field, value):
    with pytest.raises(ValueError) as error:
        settings(**{field: value})
    assert CONFIG["jwt_secret"] not in str(error.value)
    assert "private-db-password" not in str(error.value)


def test_settings_defaults_and_safe_representation():
    config = settings()
    assert config.jwt_issuer == "user-architecture-model"
    assert config.jwt_audience == "user-architecture-model-api"
    assert config.jwt_secret.get_secret_value() == CONFIG["jwt_secret"]
    assert CONFIG["jwt_secret"] not in repr(config)
    assert "private-db-password" not in repr(config)


@pytest.fixture
async def account():
    repository = FakeUserRepository()
    user = User(
        id=uuid4(),
        name="Alice",
        email="alice@example.com",
        password_hash="private-hash",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repository.add(user)
    tokens = FakeTokenService()
    token = await tokens.issue(user.id)
    return repository, user, tokens, token


@pytest.fixture
def app(account):
    repository, _, tokens, _ = account
    application = create_app(settings())
    application.dependency_overrides[get_user_repository] = lambda: repository
    application.dependency_overrides[get_token_service] = lambda: tokens

    @application.get("/protected")
    async def protected(user=Depends(get_authenticated_user)):
        return {"id": str(user.id)}

    return application


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
async def test_authentication_dependency_supports_overrides_and_case_insensitive_scheme(
    app, account, scheme
):
    _, user, _, token = account
    async with client_for(app) as client:
        response = await client.get(
            "/protected", headers={"Authorization": f"{scheme} {token.access_token}"}
        )
    assert response.status_code == 200
    assert response.json() == {"id": str(user.id)}


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer", "Bearer invalid", "invalid"])
async def test_missing_or_invalid_bearer_challenges_consistently(app, header):
    async with client_for(app) as client:
        response = await client.get(
            "/protected", headers={"Authorization": header} if header else {}
        )
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    ("error", "status", "message"),
    [
        (DependencyUnavailable(), 503, "Service unavailable"),
        (EmailAlreadyRegistered(), 409, "Email already registered"),
        (InvalidCredentials(), 401, "Invalid credentials"),
        (NotAuthenticated(), 401, "Not authenticated"),
        (RuntimeError("private-signing-secret"), 500, "Internal server error"),
    ],
)
async def test_errors_are_mapped_without_internal_details(app, error, status, message):
    @app.get("/error")
    async def fail():
        raise error

    async with client_for(app) as client:
        response = await client.get("/error")
    assert response.status_code == status
    assert response.json() == {"detail": message}
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"
    assert "private-signing-secret" not in response.text


async def test_validation_error_omits_submitted_password_input_and_context(app):
    class Body(BaseModel):
        model_config = ConfigDict(strict=True)
        password: int

    @app.post("/validation")
    async def validate(body: Body):
        return {}

    async with client_for(app) as client:
        response = await client.post("/validation", json={"password": "sensitive-password"})
    assert response.status_code == 422
    assert "sensitive-password" not in response.text
    assert response.json()["detail"][0]["loc"] == ["body", "password"]
    assert set(response.json()["detail"][0]) == {"loc", "msg", "type"}


async def test_domain_validation_is_mapped_to_422(app):
    @app.post("/domain-validation")
    async def validate():
        raise InvalidUserData("Invalid email")

    async with client_for(app) as client:
        response = await client.post("/domain-validation")
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Invalid email"


async def test_lifespan_builds_resources_and_closes_database(monkeypatch, sdk_client):
    import app.bootstrap as bootstrap

    database = Mock()
    database.close = AsyncMock()
    monkeypatch.setattr(bootstrap, "Database", Mock(return_value=database))
    app = bootstrap.create_app(settings())
    assert isinstance(app, FastAPI)
    async with client_for(app):
        assert app.state.dummy_password_hash.startswith("$argon2id$")
    database.close.assert_awaited_once()
    sdk_client.close.assert_called_once()


async def test_s3_client_startup_failure_still_disposes_database(monkeypatch):
    import app.bootstrap as bootstrap

    database = Mock()
    database.close = AsyncMock()
    monkeypatch.setattr(bootstrap, "Database", Mock(return_value=database))
    monkeypatch.setattr(
        bootstrap, "create_s3_client", Mock(side_effect=RuntimeError("startup failed"))
    )
    application = bootstrap.create_app(settings())
    with pytest.raises(RuntimeError, match="startup failed"):
        async with application.router.lifespan_context(application):
            pass
    database.close.assert_awaited_once()
