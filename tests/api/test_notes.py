"""Service-free notes HTTP contracts; bootstrap composition belongs to Lead."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import jwt
import pytest

from app.application.errors import DependencyUnavailable
from app.infrastructure.security.tokens import JwtTokenService
from app.presentation.dependencies import get_note_repository, get_token_service
from app.presentation.routers.notes import router
from tests.api.helpers import client_for
from tests.api.test_acceptance import NOW, SECRET, VARIANTS, FrozenDateTime, header_for
from tests.unit.application.fakes import FakeNoteRepository, make_note

PUBLIC_FIELDS = {"id", "title", "body", "created_at", "updated_at"}
ROUTES = [
    ("POST", "/notes"),
    ("GET", "/notes"),
    ("GET", "/notes/owned"),
    ("PATCH", "/notes/owned"),
    ("DELETE", "/notes/owned"),
]
OPERATIONS = ("add", "list_by_owner", "get_owned", "update_owned", "delete_owned")


@pytest.fixture
def note_context(api_context, file_context):
    app = api_context[0]
    # Integration 5.1: remove this inclusion when bootstrap registers the router.
    app.include_router(router)
    repo = FakeNoteRepository()
    app.dependency_overrides[get_note_repository] = lambda: repo
    return repo, file_context[1]


@pytest.fixture
async def notes_api(api_context, note_context):
    async with client_for(api_context[0]) as client:
        yield client
    assert note_context[1].calls == []


def observe_operations(repo):
    for operation in OPERATIONS:
        setattr(repo, operation, AsyncMock(wraps=getattr(repo, operation)))


def assert_no_operations(repo):
    for operation in OPERATIONS:
        getattr(repo, operation).assert_not_awaited()


def request_body(method):
    return {"json": {"title": " Title ", "body": " body\n"}} if method in ("POST", "PATCH") else {}


async def test_create_read_list_patch_delete_lifecycle(notes_api, note_context, file_auth):
    owner, headers = file_auth
    response = await notes_api.post(
        "/notes", headers=headers, json={"title": " Title\n", "body": " \nbody \n"}
    )
    assert response.status_code == 201
    created = response.json()
    assert set(created) == PUBLIC_FIELDS
    assert UUID(created["id"])
    assert created["title"] == "Title"
    assert created["body"] == " \nbody \n"
    assert created["created_at"] == created["updated_at"]
    assert datetime.fromisoformat(created["created_at"]).utcoffset() == timedelta(0)
    assert str(owner.id) not in response.text
    path = f"/notes/{created['id']}"
    fetched = await notes_api.get(path, headers=headers)
    assert fetched.status_code == 200
    assert fetched.json() == created
    assert (await notes_api.get("/notes", headers=headers)).json() == [created]
    patched = await notes_api.patch(path, headers=headers, json={"body": ""})
    assert patched.status_code == 200
    assert patched.json() == {**created, "body": "", "updated_at": patched.json()["updated_at"]}
    deleted = await notes_api.delete(path, headers=headers)
    assert deleted.status_code == 204
    assert deleted.content == b""
    for method in (notes_api.get, notes_api.delete):
        missing = await method(path, headers=headers)
        assert missing.status_code == 404
        assert missing.json() == {"detail": "Note not found"}
    assert (await notes_api.get("/notes", headers=headers)).json() == []


async def test_list_is_owned_ordered_and_ignores_owner_selector(notes_api, note_context, file_auth):
    repo, _ = note_context
    owner, headers = file_auth
    assert (await notes_api.get("/notes", headers=headers)).json() == []
    early, first, second, foreign = (
        make_note(owner.id, 3, NOW - timedelta(days=1)),
        make_note(owner.id, 1),
        make_note(owner.id, 2),
        make_note(uuid4(), 4),
    )
    for note in (second, foreign, first, early):
        await repo.add(note)
    response = await notes_api.get(f"/notes?user_id={foreign.user_id}", headers=headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        str(early.id),
        str(first.id),
        str(second.id),
    ]
    assert all(set(item) == PUBLIC_FIELDS for item in response.json())


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
async def test_foreign_and_missing_are_indistinguishable(
    notes_api, note_context, file_auth, method
):
    repo, _ = note_context
    foreign = make_note(uuid4())
    await repo.add(foreign)
    results = [
        await notes_api.request(
            method,
            f"/notes/{note_id}?user_id={foreign.user_id}",
            headers=file_auth[1],
            **request_body(method),
        )
        for note_id in (foreign.id, uuid4())
    ]
    assert all(response.status_code == 404 for response in results)
    assert results[0].json() == results[1].json() == {"detail": "Note not found"}
    assert await repo.get_owned(foreign.id, foreign.user_id) == foreign


@pytest.mark.parametrize("method", ["POST", "PATCH"])
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"title": "valid", "body": None},
        {"title": None, "body": "valid"},
        {"title": " ", "body": "valid"},
        {"title": "x" * 201, "body": "valid"},
        {"title": "valid", "body": "x" * 10001},
        *({"title": value, "body": "valid"} for value in (123, True, {}, [])),
        *({"title": "valid", "body": value} for value in (123, True, {}, [])),
        *(
            {"title": "valid", "body": "valid", key: "private-sentinel"}
            for key in ("user_id", "owner_id", "id", "created_at", "updated_at", "private-sentinel")
        ),
    ],
    ids=lambda value: None,
)
async def test_strict_input_rejected_without_any_write(
    notes_api, note_context, file_auth, method, body, caplog
):
    repo, _ = note_context
    note = make_note(file_auth[0].id)
    await repo.add(note)
    observe_operations(repo)
    path = "/notes" if method == "POST" else f"/notes/{note.id}"
    response = await notes_api.request(method, path, headers=file_auth[1], json=body)
    assert response.status_code == 422
    assert "private-sentinel" not in response.text
    assert "private-sentinel" not in caplog.text
    assert all(set(error) == {"loc", "msg", "type"} for error in response.json()["detail"])
    assert_no_operations(repo)
    assert await repo.get_owned(note.id, note.user_id) == note


@pytest.mark.parametrize("body", [{"title": "valid"}, {"body": "valid"}])
async def test_creation_requires_both_fields(notes_api, note_context, file_auth, body):
    response = await notes_api.post("/notes", headers=file_auth[1], json=body)
    assert response.status_code == 422
    assert await note_context[0].list_by_owner(file_auth[0].id) == []


@pytest.mark.parametrize("method", ["POST", "PATCH"])
@pytest.mark.parametrize(
    "raw", ["null", "[]", '"private-sentinel"', "123", "true", '{"title":', ""]
)
async def test_invalid_json_structure_is_sanitized(notes_api, note_context, file_auth, method, raw):
    repo = note_context[0]
    observe_operations(repo)
    response = await notes_api.request(
        method,
        "/notes" if method == "POST" else f"/notes/{uuid4()}",
        headers={**file_auth[1], "Content-Type": "application/json"},
        content=raw,
    )
    assert response.status_code == 422
    assert "private-sentinel" not in response.text
    assert all(set(error) == {"loc", "msg", "type"} for error in response.json()["detail"])
    assert_no_operations(repo)


@pytest.mark.parametrize("method", ["POST", "PATCH"])
@pytest.mark.parametrize(
    "title,body",
    [(" x ", ""), (" " + "x" * 200 + " ", " body\n"), ("title", "x" * 10000)],
    ids=["minimum", "max-title", "max-body"],
)
async def test_inclusive_limits_normalization_and_duplicates(
    notes_api, note_context, file_auth, method, title, body
):
    note = make_note(file_auth[0].id)
    await note_context[0].add(note)
    response = await notes_api.request(
        method,
        "/notes" if method == "POST" else f"/notes/{note.id}",
        headers=file_auth[1],
        json={"title": title, "body": body},
    )
    assert response.status_code == (201 if method == "POST" else 200)
    assert response.json()["title"] == title.strip()
    assert response.json()["body"] == body
    assert set(response.json()) == PUBLIC_FIELDS
    duplicate = await notes_api.post(
        "/notes", headers=file_auth[1], json={"title": title, "body": body}
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] != response.json()["id"]


@pytest.mark.parametrize(
    "changes",
    [{"title": " new "}, {"body": ""}, {"title": "new", "body": "new\n"}, {"title": "Sample"}],
)
async def test_patch_preserves_omitted_fields_and_creation_time(
    notes_api, note_context, file_auth, changes
):
    note = make_note(file_auth[0].id)
    await note_context[0].add(note)
    response = await notes_api.patch(f"/notes/{note.id}", headers=file_auth[1], json=changes)
    assert response.status_code == 200
    assert response.json() == dict(
        id=str(note.id),
        title=changes.get("title", "Sample").strip(),
        body=changes.get("body", " original body\n"),
        created_at="2026-01-01T00:00:00Z",
        updated_at=response.json()["updated_at"],
    )
    assert response.json()["updated_at"] != "2026-01-01T00:00:00Z"


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
async def test_path_uuid_validation_follows_authentication(
    notes_api, note_context, file_auth, method
):
    repo = note_context[0]
    observe_operations(repo)
    for authenticated in (False, True):
        response = await notes_api.request(
            method,
            "/notes/not-a-uuid",
            headers=file_auth[1] if authenticated else {},
            **request_body(method),
        )
        assert response.status_code == (422 if authenticated else 401)
        if authenticated:
            assert response.json()["detail"][0]["loc"] == ["path", "note_id"]
        else:
            assert response.json() == {"detail": "Not authenticated"}
            assert response.headers["www-authenticate"] == "Bearer"
    assert_no_operations(repo)


@pytest.fixture
def note_jwt(api_context, monkeypatch):
    service = JwtTokenService(SECRET, clock=lambda: NOW)
    api_context[0].dependency_overrides[get_token_service] = lambda: service
    monkeypatch.setattr(jwt.api_jwt, "datetime", FrozenDateTime)
    return service


@pytest.mark.parametrize("method,path", ROUTES)
@pytest.mark.parametrize("variant", VARIANTS)
async def test_existing_jwt_rejection_matrix_on_all_note_routes(
    notes_api, note_context, file_auth, note_jwt, method, path, variant
):
    repo = note_context[0]
    observe_operations(repo)
    headers = header_for(file_auth[0].id, variant)
    response = await notes_api.request(
        method, path.replace("owned", "not-a-uuid"), headers=headers, **request_body(method)
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert_no_operations(repo)


@pytest.mark.parametrize("method,path", ROUTES)
@pytest.mark.parametrize("elapsed", [0, 3599])
async def test_real_valid_jwt_on_all_note_routes(
    notes_api, note_context, file_auth, note_jwt, monkeypatch, method, path, elapsed
):
    note = make_note(file_auth[0].id)
    await note_context[0].add(note)
    token = await note_jwt.issue(file_auth[0].id)
    monkeypatch.setattr(FrozenDateTime, "current", NOW + timedelta(seconds=elapsed))
    response = await notes_api.request(
        method,
        path.replace("owned", str(note.id)),
        headers={"Authorization": f"bearer {token.access_token}"},
        **request_body(method),
    )
    assert response.status_code == (201 if method == "POST" else 204 if method == "DELETE" else 200)


@pytest.mark.parametrize("method,path", ROUTES)
@pytest.mark.parametrize("failure", ["read", "verify"])
async def test_authentication_outage_never_reaches_notes(
    notes_api, api_context, note_context, file_auth, method, path, failure
):
    repo = note_context[0]
    observe_operations(repo)
    api_context[1].fail_reads = failure == "read"
    api_context[3].fail_verify = failure == "verify"
    response = await notes_api.request(
        method, path.replace("owned", "not-a-uuid"), headers=file_auth[1], **request_body(method)
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}
    assert_no_operations(repo)


@pytest.mark.parametrize(
    "method,path,operation",
    [
        ("POST", "/notes", "add"),
        ("GET", "/notes", "list_by_owner"),
        ("GET", "/notes/owned", "get_owned"),
        ("PATCH", "/notes/owned", "update_owned"),
        ("DELETE", "/notes/owned", "delete_owned"),
    ],
)
@pytest.mark.parametrize("unexpected", [False, True])
async def test_failures_are_sanitized_and_leave_state_intact(
    notes_api, note_context, file_auth, monkeypatch, caplog, method, path, operation, unexpected
):
    repo = note_context[0]
    note = make_note(file_auth[0].id)
    await repo.add(note)
    error = RuntimeError("private-sql-credential") if unexpected else DependencyUnavailable()
    with monkeypatch.context() as patch:
        patch.setattr(repo, operation, AsyncMock(side_effect=error))
        response = await notes_api.request(
            method,
            path.replace("owned", str(note.id)),
            headers=file_auth[1],
            **request_body(method),
        )
    assert response.status_code == (500 if unexpected else 503)
    assert response.json() == {
        "detail": "Internal server error" if unexpected else "Service unavailable"
    }
    assert "private-sql-credential" not in response.text
    assert "private-sql-credential" not in caplog.text
    assert await repo.list_by_owner(note.user_id) == [note]


async def test_concurrent_patches_and_deletes_with_fake(notes_api, note_context, file_auth):
    note = make_note(file_auth[0].id)
    await note_context[0].add(note)
    path = f"/notes/{note.id}"
    patched = await asyncio.gather(
        notes_api.patch(path, headers=file_auth[1], json={"title": "new"}),
        notes_api.patch(path, headers=file_auth[1], json={"body": "new body"}),
    )
    assert [response.status_code for response in patched] == [200, 200]
    result = (await notes_api.get(path, headers=file_auth[1])).json()
    assert (result["title"], result["body"]) == ("new", "new body")
    removed = await asyncio.gather(
        notes_api.delete(path, headers=file_auth[1]), notes_api.delete(path, headers=file_auth[1])
    )
    assert sorted(response.status_code for response in removed) == [204, 404]
    assert (
        await notes_api.patch(path, headers=file_auth[1], json={"title": "gone"})
    ).status_code == 404
