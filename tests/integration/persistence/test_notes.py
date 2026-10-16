"""PostgreSQL acceptance for notes; requires an explicit disposable TEST_DATABASE_URL."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, insert, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

from app.application.dto import NotePatch
from app.application.errors import DependencyUnavailable
from app.domain.entities import Note, User
from app.infrastructure.persistence.models import NoteModel, UserModel
from app.infrastructure.persistence.note_repository import SqlAlchemyNoteRepository
from app.infrastructure.persistence.user_repository import SqlAlchemyUserRepository

pytestmark = pytest.mark.integration
NOW = datetime(2026, 1, 1, tzinfo=UTC)
EDITED = datetime(2026, 1, 2, tzinfo=UTC)


async def seed_owner(database):
    owner = User(uuid4(), "Alice", f"{uuid4().hex}@example.com", "hash", NOW)
    async with database.session() as session:
        await SqlAlchemyUserRepository(session).add(owner)
    return owner.id


def make_note(owner, number=1, created_at=NOW, **fields):
    return Note(
        UUID(int=number),
        owner,
        fields.get("title", "Private"),
        fields.get("body", "  body\n"),
        created_at,
        created_at,
    )


async def test_committed_roundtrip_owner_filters_duplicates_and_order(database):
    owner, other = await seed_owner(database), await seed_owner(database)
    first, second = make_note(owner, 1), make_note(owner, 2)
    early = make_note(owner, 3, datetime(2025, 1, 1, tzinfo=UTC))
    foreign = make_note(other, 4)
    async with database.session() as writer:
        repo = SqlAlchemyNoteRepository(writer)
        for note in (second, foreign, first, early):
            await repo.add(note)
        # Observe commits while the writer's session is still open.
        async with database.session() as reader:
            read_repo = SqlAlchemyNoteRepository(reader)
            assert await read_repo.list_by_owner(owner) == [early, first, second]
            assert await read_repo.list_by_owner(uuid4()) == []
            assert await read_repo.get_owned(first.id, owner) == first
            assert await read_repo.get_owned(first.id, other) is None
            assert await read_repo.get_owned(uuid4(), owner) is None
        assert await repo.update_owned(first.id, other, NotePatch(title="Intruder"), EDITED) is None
        assert await repo.update_owned(uuid4(), owner, NotePatch(body=""), EDITED) is None
        assert await repo.delete_owned(first.id, other) is False
        assert await repo.delete_owned(uuid4(), owner) is False
        assert await repo.delete_owned(first.id, owner) is True
        assert await repo.delete_owned(first.id, owner) is False
        async with database.session() as reader:
            read_repo = SqlAlchemyNoteRepository(reader)
            assert await read_repo.get_owned(first.id, owner) is None
            assert await read_repo.get_owned(second.id, owner) == second
            assert await read_repo.get_owned(foreign.id, other) == foreign


@pytest.mark.parametrize(
    "fields",
    [
        {"title": "New"},
        {"body": ""},
        {"title": "New", "body": " \n "},
        {"title": "Private"},
        {"title": "x" * 200, "body": "\U0001f642" * 10000},
    ],
)
async def test_patch_commits_only_present_fields_and_refreshes_timestamp(database, fields):
    owner = await seed_owner(database)
    note = make_note(owner)
    async with database.session() as writer:
        repo = SqlAlchemyNoteRepository(writer)
        await repo.add(note)
        expected = replace(note, **fields, updated_at=EDITED)
        assert await repo.update_owned(note.id, owner, NotePatch(**fields), EDITED) == expected
        async with database.session() as reader:
            assert await SqlAlchemyNoteRepository(reader).get_owned(note.id, owner) == expected


async def test_foreign_key_and_duplicate_id_failures_rollback_and_allow_reuse(database):
    owner = await seed_owner(database)
    note = make_note(owner)
    async with database.session() as session:
        repo = SqlAlchemyNoteRepository(session)
        with pytest.raises(DependencyUnavailable):
            await repo.add(replace(note, user_id=uuid4()))
        await repo.add(note)
        with pytest.raises(DependencyUnavailable):
            await repo.add(replace(note, body="must not overwrite"))
        assert await repo.get_owned(note.id, owner) == note
        with pytest.raises(IntegrityError):
            await session.execute(delete(UserModel).where(UserModel.id == owner))
        await session.rollback()
        assert await repo.get_owned(note.id, owner) == note


@pytest.mark.parametrize(
    "title,body,valid",
    [
        ("", "", False),
        ("x" * 201, "", False),
        ("Title", "x" * 10001, False),
        (None, "", False),
        ("Title", None, False),
        ("x", "", True),
        ("\U0001f642" * 200, "\U0001f642" * 10000, True),
    ],
    ids=[
        "empty-title",
        "long-title",
        "long-body",
        "null-title",
        "null-body",
        "minimum",
        "unicode-maximum",
    ],
)
async def test_database_rejects_invalid_raw_writes_and_accepts_inclusive_limits(
    database, title, body, valid
):
    owner = await seed_owner(database)
    async with database.session() as session:
        values = dict(
            id=uuid4(), user_id=owner, title=title, body=body, created_at=NOW, updated_at=NOW
        )
        if valid:
            await session.execute(insert(NoteModel).values(**values))
            await session.commit()
        else:
            with pytest.raises(DBAPIError):
                await session.execute(insert(NoteModel).values(**values))
            await session.rollback()


@pytest.mark.parametrize("operation", ["add", "update", "delete"])
async def test_commit_failure_rolls_back_all_fields_and_allows_session_reuse(
    database, monkeypatch, operation
):
    owner = await seed_owner(database)
    note = make_note(owner)
    async with database.session() as session:
        repo = SqlAlchemyNoteRepository(session)
        if operation != "add":
            await repo.add(note)
        real_commit = session.commit

        async def fail_commit():
            await session.flush()
            raise OperationalError("private commit", {}, RuntimeError("secret"))

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(DependencyUnavailable, match="^Service unavailable$") as caught:
            if operation == "add":
                await repo.add(note)
            elif operation == "update":
                await repo.update_owned(note.id, owner, NotePatch(title="New", body=""), EDITED)
            else:
                await repo.delete_owned(note.id, owner)
        assert caught.value.__suppress_context__
        monkeypatch.setattr(session, "commit", real_commit)
        expected = None if operation == "add" else note
        assert await repo.get_owned(note.id, owner) == expected
        async with database.session() as reader:
            assert await SqlAlchemyNoteRepository(reader).get_owned(note.id, owner) == expected
        if operation == "add":
            await repo.add(note)
        elif operation == "update":
            assert await repo.update_owned(note.id, owner, NotePatch(body=""), EDITED) == replace(
                note, body="", updated_at=EDITED
            )
        else:
            assert await repo.delete_owned(note.id, owner) is True


@pytest.mark.parametrize("operation", ["list", "get", "update", "delete"])
async def test_query_failures_are_sanitized(database, monkeypatch, operation):
    async with database.session() as session:
        monkeypatch.setattr(
            session,
            "execute",
            AsyncMock(side_effect=OperationalError("private query", {}, RuntimeError("secret"))),
        )
        repo, owner, note_id = SqlAlchemyNoteRepository(session), uuid4(), uuid4()
        with pytest.raises(DependencyUnavailable, match="^Service unavailable$") as caught:
            if operation == "list":
                await repo.list_by_owner(owner)
            elif operation == "get":
                await repo.get_owned(note_id, owner)
            elif operation == "update":
                await repo.update_owned(note_id, owner, NotePatch(body=""), EDITED)
            else:
                await repo.delete_owned(note_id, owner)
        assert caught.value.__suppress_context__


async def wait_until_blocked(database, waiter_pid, blocker_pid):
    """Observe a PostgreSQL lock dependency; a delay is never evidence of ordering."""

    async def observe():
        async with database.session() as observer:
            while True:
                blockers = await observer.scalar(
                    text("SELECT pg_blocking_pids(:pid)"), {"pid": waiter_pid}
                )
                if blocker_pid in blockers:
                    return

    await asyncio.wait_for(observe(), timeout=10)


@pytest.mark.parametrize(
    "first_action,second_action",
    [
        ("title", "body"),
        ("title", "title"),
        ("delete", "title"),
        ("delete", "delete"),
    ],
)
async def test_competing_writes_follow_observed_row_lock_order(
    database, monkeypatch, first_action, second_action
):
    owner = await seed_owner(database)
    note = make_note(owner)
    async with database.session() as session:
        await SqlAlchemyNoteRepository(session).add(note)

    async with database.session() as first_session, database.session() as second_session:
        first_pid = await first_session.scalar(text("SELECT pg_backend_pid()"))
        second_pid = await second_session.scalar(text("SELECT pg_backend_pid()"))
        # Keep stale ORM instances alive to exercise RETURNING identity-map refresh too.
        stale_first = await first_session.get(NoteModel, note.id)
        stale_second = await second_session.get(NoteModel, note.id)
        assert stale_first.title == stale_second.title == "Private"
        first_has_written, release_first = asyncio.Event(), asyncio.Event()
        real_commit = first_session.commit

        async def hold_commit():
            first_has_written.set()
            await release_first.wait()
            await real_commit()

        monkeypatch.setattr(first_session, "commit", hold_commit)

        async def write(session, action, value, timestamp):
            repo = SqlAlchemyNoteRepository(session)
            if action == "delete":
                return await repo.delete_owned(note.id, owner)
            return await repo.update_owned(note.id, owner, NotePatch(**{action: value}), timestamp)

        first = asyncio.create_task(write(first_session, first_action, "First", EDITED))
        second = None
        try:
            await asyncio.wait_for(first_has_written.wait(), timeout=10)
            # An earlier clock value intentionally cannot control which write wins.
            second = asyncio.create_task(write(second_session, second_action, "Second", NOW))
            await wait_until_blocked(database, second_pid, first_pid)
            release_first.set()
            first_result, second_result = await asyncio.wait_for(
                asyncio.gather(first, second), timeout=10
            )
        finally:
            release_first.set()
            for task in (first, second):
                if task is not None and not task.done():
                    task.cancel()
            await asyncio.gather(
                *(task for task in (first, second) if task), return_exceptions=True
            )

        if first_action == "delete":
            assert first_result is True
            assert second_result is (False if second_action == "delete" else None)
            expected = None
        else:
            assert first_result == replace(note, title="First", updated_at=EDITED)
            expected = replace(
                note,
                title="Second" if second_action == "title" else "First",
                body="Second" if second_action == "body" else note.body,
                updated_at=NOW,
            )
            assert second_result == expected
        async with database.session() as reader:
            assert await SqlAlchemyNoteRepository(reader).get_owned(note.id, owner) == expected


async def test_database_rejects_entire_invalid_patch_including_timestamp(database):
    owner = await seed_owner(database)
    note = make_note(owner)
    async with database.session() as session:
        repo = SqlAlchemyNoteRepository(session)
        await repo.add(note)
        with pytest.raises(IntegrityError):
            await session.execute(
                update(NoteModel)
                .where(NoteModel.id == note.id)
                .values(title="New", body="x" * 10001, updated_at=EDITED)
            )
        await session.rollback()
        assert await repo.get_owned(note.id, owner) == note
