import pytest

from app.bootstrap import create_app
from app.infrastructure.settings import Settings
from app.presentation.dependencies import (
    get_file_repository,
    get_file_storage,
    get_password_hasher,
    get_token_service,
    get_user_repository,
)
from tests.api.helpers import client_for
from tests.unit.application.fakes import (
    FakeFileRepository,
    FakeFileStorage,
    FakePasswordHasher,
    FakeTokenService,
    FakeUserRepository,
)


@pytest.fixture
def api_context():
    app = create_app(
        Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://test:test@127.0.0.1:1/test",
            jwt_secret="test-only-secret-at-least-32-bytes-long",
            s3_bucket="test-bucket",
        )
    )
    repository, hasher, tokens = FakeUserRepository(), FakePasswordHasher(), FakeTokenService()
    app.dependency_overrides[get_user_repository] = lambda: repository
    app.dependency_overrides[get_password_hasher] = lambda: hasher
    app.dependency_overrides[get_token_service] = lambda: tokens
    return app, repository, hasher, tokens


@pytest.fixture
async def api(api_context):
    async with client_for(api_context[0]) as client:
        yield client


@pytest.fixture
def file_context(api_context):
    app = api_context[0]
    repository, storage = FakeFileRepository(), FakeFileStorage()
    app.dependency_overrides[get_file_repository] = lambda: repository
    app.dependency_overrides[get_file_storage] = lambda: storage
    return repository, storage


@pytest.fixture
async def file_auth(api, api_context):
    from datetime import UTC, datetime
    from uuid import uuid4

    from app.domain.entities import User

    user = User(
        uuid4(), "Alice", "alice@example.com", "private-hash", datetime(2026, 1, 1, tzinfo=UTC)
    )
    await api_context[1].add(user)
    token = await api_context[3].issue(user.id)
    return user, {"Authorization": f"Bearer {token.access_token}"}


@pytest.fixture(autouse=True)
def sdk_client(monkeypatch):
    from unittest.mock import Mock

    import app.bootstrap as bootstrap

    client = Mock()
    monkeypatch.setattr(bootstrap, "create_s3_client", Mock(return_value=client))
    return client
