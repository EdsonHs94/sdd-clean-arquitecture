from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

from app.application.errors import DependencyUnavailable, NoteNotFound
from app.application.use_cases.create_note import CreateNote
from app.application.use_cases.delete_user_note import DeleteUserNote
from app.application.use_cases.get_user_note import GetUserNote
from app.application.use_cases.list_user_notes import ListUserNotes
from app.application.use_cases.update_user_note import UpdateUserNote
from app.domain.errors import InvalidNoteData
from tests.unit.application.fakes import FakeNoteRepository, make_note

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PUBLIC_FIELDS = {"id", "title", "body", "created_at", "updated_at"}


async def test_create_normalizes_title_preserves_body_and_uses_one_clock_read():
    repo, owner, note_id = FakeNoteRepository(), uuid4(), uuid4()
    clock = Mock(return_value=NOW)
    result = await CreateNote(repo, clock=clock, id_factory=lambda: note_id).execute(
        owner, "  Title\n", " \nbody \n"
    )
    assert asdict(result) == dict(
        id=note_id, title="Title", body=" \nbody \n", created_at=NOW, updated_at=NOW
    )
    assert await repo.get_owned(note_id, owner) == replace(
        make_note(owner), id=note_id, title="Title", body=" \nbody \n"
    )
    clock.assert_called_once_with()


async def test_repeated_creations_have_unique_ids_and_allow_same_title():
    repo, owner = FakeNoteRepository(), uuid4()
    create = CreateNote(repo)
    first, second = await create.execute(owner, "same", ""), await create.execute(owner, "same", "")
    assert isinstance(first.id, UUID)
    assert first.id != second.id
    assert len(await repo.list_by_owner(owner)) == 2


@pytest.mark.parametrize(
    "title,body",
    [("", ""), (" \n", ""), ("a" * 201, ""), (123, ""), ("title", None), ("title", "a" * 10001)],
)
async def test_invalid_create_never_writes_or_reads_clock(title, body):
    repo, owner = FakeNoteRepository(fail_writes=True), uuid4()
    clock = Mock(side_effect=AssertionError("Invalid input must precede clock"))
    with pytest.raises(InvalidNoteData):
        await CreateNote(repo, clock=clock).execute(owner, title, body)
    assert await repo.list_by_owner(owner) == []


@pytest.mark.parametrize("title,body", [(" x ", ""), (" " + "x" * 200 + " ", "x" * 10000)])
async def test_create_accepts_inclusive_limits(title, body):
    result = await CreateNote(FakeNoteRepository()).execute(uuid4(), title, body)
    assert result.title == title.strip()
    assert result.body == body


async def test_listing_is_owned_ordered_and_safely_projected():
    repo, owner = FakeNoteRepository(), uuid4()
    assert await ListUserNotes(repo).execute(owner) == []
    for note in (
        make_note(owner, 2),
        make_note(uuid4(), 4),
        make_note(owner, 1),
        make_note(owner, 3, NOW - timedelta(days=1)),
    ):
        await repo.add(note)
    results = await ListUserNotes(repo).execute(owner)
    assert [result.id for result in results] == [UUID(int=3), UUID(int=1), UUID(int=2)]
    assert all(set(asdict(result)) == PUBLIC_FIELDS for result in results)


async def test_get_projects_only_public_fields():
    repo, owner = FakeNoteRepository(), uuid4()
    note = make_note(owner)
    await repo.add(note)
    result = await GetUserNote(repo).execute(owner, note.id)
    assert asdict(result) == dict(
        id=note.id, title="Sample", body=" original body\n", created_at=NOW, updated_at=NOW
    )


@pytest.mark.parametrize(
    "changes,expected_title,expected_body",
    [
        ({"title": " new "}, "new", " original body\n"),
        ({"body": ""}, "Sample", ""),
        ({"title": " new ", "body": " new\n"}, "new", " new\n"),
        ({"title": "Sample"}, "Sample", " original body\n"),
    ],
)
async def test_update_is_atomic_without_preread_and_always_reassigns_timestamp(
    changes, expected_title, expected_body
):
    repo, owner = FakeNoteRepository(fail_reads=True), uuid4()
    note = make_note(owner)
    await repo.add(note)
    later = NOW + timedelta(seconds=1)
    clock = Mock(return_value=later)
    result = await UpdateUserNote(repo, clock=clock).execute(owner, note.id, **changes)
    assert asdict(result) == dict(
        id=note.id, title=expected_title, body=expected_body, created_at=NOW, updated_at=later
    )
    clock.assert_called_once_with()
    repo.fail_reads = False
    assert await repo.get_owned(note.id, owner) == replace(
        note, title=expected_title, body=expected_body, updated_at=later
    )


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"title": " "},
        {"body": "x" * 10001},
        {"title": "valid", "body": 1},
        {"title": "x" * 201, "body": "valid"},
    ],
)
async def test_invalid_update_preserves_fields_and_timestamp_without_write(changes):
    repo, owner = FakeNoteRepository(), uuid4()
    note = make_note(owner)
    await repo.add(note)
    repo.fail_writes = True
    clock = Mock(side_effect=AssertionError("Invalid input must precede clock"))
    with pytest.raises(InvalidNoteData):
        await UpdateUserNote(repo, clock=clock).execute(owner, note.id, **changes)
    assert await repo.get_owned(note.id, owner) == note


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
async def test_foreign_and_missing_are_not_found_and_preserve_foreign_note(operation):
    repo, owner = FakeNoteRepository(), uuid4()
    note = make_note(uuid4())
    await repo.add(note)
    for note_id in (note.id, uuid4()):
        with pytest.raises(NoteNotFound):
            if operation == "get":
                await GetUserNote(repo).execute(owner, note_id)
            elif operation == "update":
                await UpdateUserNote(repo).execute(owner, note_id, title="new")
            else:
                await DeleteUserNote(repo).execute(owner, note_id)
    assert await repo.get_owned(note.id, note.user_id) == note


async def test_delete_removes_owned_note_and_cannot_be_repeated_or_updated():
    repo, owner = FakeNoteRepository(fail_reads=True), uuid4()
    note = make_note(owner)
    await repo.add(note)
    assert await DeleteUserNote(repo).execute(owner, note.id) is None
    with pytest.raises(NoteNotFound):
        await DeleteUserNote(repo).execute(owner, note.id)
    with pytest.raises(NoteNotFound):
        await UpdateUserNote(repo).execute(owner, note.id, body="new")
    repo.fail_reads = False
    assert await repo.list_by_owner(owner) == []


@pytest.mark.parametrize("operation", ["create", "list", "get", "update", "delete"])
async def test_dependency_outages_propagate_without_mutation(operation):
    repo, owner = FakeNoteRepository(), uuid4()
    note = make_note(owner)
    await repo.add(note)
    repo.fail_reads = repo.fail_writes = True
    with pytest.raises(DependencyUnavailable):
        if operation == "create":
            await CreateNote(repo).execute(owner, "new", "")
        elif operation == "list":
            await ListUserNotes(repo).execute(owner)
        elif operation == "get":
            await GetUserNote(repo).execute(owner, note.id)
        elif operation == "update":
            await UpdateUserNote(repo).execute(owner, note.id, title="new", body="new")
        else:
            await DeleteUserNote(repo).execute(owner, note.id)
    repo.fail_reads = False
    assert await repo.list_by_owner(owner) == [note]
