import httpx
import pytest
from fastapi import FastAPI

from app.application.errors import NoteNotFound
from app.domain.errors import InvalidNoteData
from app.presentation.error_handlers import install_error_handlers


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (NoteNotFound(), 404, "Note not found"),
        (
            InvalidNoteData("Invalid note"),
            422,
            [{"loc": ["body"], "msg": "Invalid note", "type": "value_error"}],
        ),
    ],
)
async def test_note_errors_have_safe_http_contract(error, status, detail):
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/failure")
    async def failure():
        raise error

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/failure")
    assert response.status_code == status
    assert response.json() == {"detail": detail}
