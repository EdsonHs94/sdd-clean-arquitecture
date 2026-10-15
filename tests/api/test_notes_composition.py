import pytest


async def test_composition_installs_note_repository_factory(monkeypatch):
    from unittest.mock import AsyncMock, Mock

    import app.bootstrap as bootstrap
    from app.infrastructure.persistence.note_repository import SqlAlchemyNoteRepository
    from tests.api.helpers import client_for
    from tests.api.test_app import settings

    database = Mock()
    database.close = AsyncMock()
    monkeypatch.setattr(bootstrap, "Database", Mock(return_value=database))
    app = bootstrap.create_app(settings())
    async with client_for(app):
        assert app.state.note_repository_factory is SqlAlchemyNoteRepository


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/notes"),
        ("GET", "/notes"),
        ("GET", "/notes/00000000-0000-0000-0000-000000000001"),
        ("PATCH", "/notes/00000000-0000-0000-0000-000000000001"),
        ("DELETE", "/notes/00000000-0000-0000-0000-000000000001"),
    ],
)
async def test_composed_app_exposes_protected_note_operations(api, method, path):
    response = await api.request(method, path, json={"title": "Hello", "body": ""})
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"
