"""Service-free checks of SQL and transaction/error boundaries, not PostgreSQL acceptance."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import Result
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto import NotePatch
from app.application.errors import DependencyUnavailable
from app.domain.entities import Note
from app.infrastructure.persistence.models import NoteModel

NOW = datetime(2026, 1, 1, tzinfo=UTC)
EDITED = datetime(2026, 1, 2, tzinfo=UTC)


def make_session():
    session = MagicMock(spec=AsyncSession)
    # execute is async, but its buffered Result and scalar accessors are synchronous.
    session.execute.return_value = MagicMock(spec=Result)
    return session


def repository(session):
    from app.infrastructure.persistence.note_repository import SqlAlchemyNoteRepository

    return SqlAlchemyNoteRepository(session)


def make_note():
    return Note(uuid4(), uuid4(), "Private", "  body\n", NOW, NOW)


def model_for(note):
    return NoteModel(
        id=note.id,
        user_id=note.user_id,
        title=note.title,
        body=note.body,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def compiled_query(session):
    return session.execute.call_args.args[0].compile(dialect=dialect())


async def test_add_maps_domain_fields_and_waits_for_commit():
    session, note = make_session(), make_note()
    events = []

    async def commit():
        events.append("committed")

    session.commit.side_effect = commit
    assert await repository(session).add(note) is None
    events.append("returned")
    assert events == ["committed", "returned"]
    model = session.add.call_args.args[0]
    assert (
        model.id,
        model.user_id,
        model.title,
        model.body,
        model.created_at,
        model.updated_at,
    ) == (note.id, note.user_id, "Private", "  body\n", NOW, NOW)


@pytest.mark.parametrize(
    "changes,fields",
    [
        (NotePatch(title="New"), {"title": "New", "updated_at": EDITED}),
        (NotePatch(body=""), {"body": "", "updated_at": EDITED}),
        (NotePatch(title="New", body="\n"), {"title": "New", "body": "\n", "updated_at": EDITED}),
    ],
)
async def test_patch_emits_only_present_fields_with_owner_predicate_and_returning(changes, fields):
    session, note = make_session(), make_note()
    model = model_for(note)
    for name, value in fields.items():
        setattr(model, name, value)
    session.execute.return_value.scalar_one_or_none.return_value = model
    events = []

    async def commit():
        events.append("committed")

    session.commit.side_effect = commit
    result = await repository(session).update_owned(note.id, note.user_id, changes, EDITED)
    events.append("returned")
    assert events == ["committed", "returned"]
    assert result == Note(
        note.id,
        note.user_id,
        fields.get("title", "Private"),
        fields.get("body", "  body\n"),
        NOW,
        EDITED,
    )
    compiled = compiled_query(session)
    sql = str(compiled)
    assert sql.startswith("UPDATE notes SET ")
    assert "WHERE notes.id =" in sql and "AND notes.user_id =" in sql
    assert "RETURNING notes.id" in sql
    assignments = sql.split(" SET ", 1)[1].split(" WHERE ", 1)[0]
    assert {part.strip().split("=", 1)[0] for part in assignments.split(",")} == set(fields)
    assert compiled.params == {**fields, "id_1": note.id, "user_id_1": note.user_id}


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
async def test_absence_maps_to_contract_result(operation):
    session, note = make_session(), make_note()
    session.execute.return_value.scalar_one_or_none.return_value = None
    repo = repository(session)
    if operation == "get":
        assert await repo.get_owned(note.id, note.user_id) is None
    elif operation == "update":
        assert await repo.update_owned(note.id, note.user_id, NotePatch(body=""), EDITED) is None
        session.commit.assert_awaited_once()
    else:
        assert await repo.delete_owned(note.id, note.user_id) is False
        session.commit.assert_awaited_once()
    sql = str(compiled_query(session))
    assert "WHERE notes.id =" in sql and "AND notes.user_id =" in sql


async def test_list_uses_owner_creation_and_uuid_order_and_returns_domain_entities():
    session, note = make_session(), make_note()
    session.execute.return_value.scalars.return_value = [model_for(note)]
    assert await repository(session).list_by_owner(note.user_id) == [note]
    compiled = compiled_query(session)
    assert "WHERE notes.user_id =" in str(compiled)
    assert "ORDER BY notes.created_at, notes.id" in str(compiled)
    assert compiled.params == {"user_id_1": note.user_id}


@pytest.mark.parametrize("operation", ["add", "update", "delete", "list", "get"])
@pytest.mark.parametrize("error_type", [OperationalError, OSError])
async def test_operational_errors_are_sanitized_and_failed_writes_rollback(operation, error_type):
    session, note = make_session(), make_note()
    error = (
        OperationalError("private SQL", {}, RuntimeError("secret"))
        if error_type is OperationalError
        else OSError("private connection")
    )
    if operation == "add":
        session.commit.side_effect = error
    else:
        session.execute.side_effect = error
    repo = repository(session)
    with pytest.raises(DependencyUnavailable, match="^Service unavailable$") as caught:
        if operation == "add":
            await repo.add(note)
        elif operation == "update":
            await repo.update_owned(note.id, note.user_id, NotePatch(body=""), EDITED)
        elif operation == "delete":
            await repo.delete_owned(note.id, note.user_id)
        elif operation == "list":
            await repo.list_by_owner(note.user_id)
        else:
            await repo.get_owned(note.id, note.user_id)
    assert caught.value.__suppress_context__
    if operation in {"add", "update", "delete"}:
        session.rollback.assert_awaited_once()


@pytest.mark.parametrize("operation", ["update", "delete"])
async def test_commit_failure_never_returns_write_success(operation):
    session, note = make_session(), make_note()
    session.execute.return_value.scalar_one_or_none.return_value = (
        model_for(note) if operation == "update" else note.id
    )
    session.commit.side_effect = OSError("private commit failure")
    repo = repository(session)
    with pytest.raises(DependencyUnavailable, match="^Service unavailable$"):
        if operation == "update":
            await repo.update_owned(note.id, note.user_id, NotePatch(body=""), EDITED)
        else:
            await repo.delete_owned(note.id, note.user_id)
    session.rollback.assert_awaited_once()


@pytest.mark.parametrize(
    "rollback_error",
    [OSError("private rollback"), OperationalError("rollback", {}, RuntimeError("secret"))],
)
async def test_rollback_failure_is_also_sanitized(rollback_error):
    session = make_session()
    session.commit.side_effect = OSError("private commit")
    session.rollback.side_effect = rollback_error
    with pytest.raises(DependencyUnavailable, match="^Service unavailable$") as caught:
        await repository(session).add(make_note())
    assert caught.value.__suppress_context__
