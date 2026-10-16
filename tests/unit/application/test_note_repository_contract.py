"""Observable note repository contract; persistence uses the same behavior matrix."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.dto import NotePatch
from app.application.errors import DependencyUnavailable
from tests.unit.application.fakes import FakeNoteRepository, make_note


async def test_owned_operations_hide_foreign_and_missing_notes():
    repo, owner, foreign = FakeNoteRepository(), uuid4(), uuid4()
    note = make_note(owner)
    await repo.add(note)
    assert await repo.get_owned(note.id, owner) == note
    for note_id in (note.id, uuid4()):
        assert await repo.get_owned(note_id, foreign) is None
        assert (
            await repo.update_owned(note_id, foreign, NotePatch(title="new"), note.updated_at)
            is None
        )
        assert await repo.delete_owned(note_id, foreign) is False
    assert await repo.list_by_owner(foreign) == []
    assert await repo.list_by_owner(owner) == [note]


async def test_duplicate_titles_and_order_by_creation_then_uuid():
    repo, owner = FakeNoteRepository(), uuid4()
    first, second = make_note(owner, 1), make_note(owner, 2)
    early = make_note(owner, 3, datetime(2025, 1, 1, tzinfo=UTC))
    for note in (second, make_note(uuid4(), 4), early, first):
        await repo.add(note)
    assert await repo.list_by_owner(owner) == [early, first, second]


@pytest.mark.parametrize(
    "changes", [NotePatch(title="new"), NotePatch(body=""), NotePatch(title="new", body="new body")]
)
async def test_patch_changes_only_present_fields_and_updated_time(changes):
    repo, owner = FakeNoteRepository(), uuid4()
    note = make_note(owner)
    await repo.add(note)
    later = note.updated_at + timedelta(seconds=1)
    updated = await repo.update_owned(note.id, owner, changes, later)
    expected = replace(
        note,
        title=changes.title if changes.title is not None else note.title,
        body=changes.body if changes.body is not None else note.body,
        updated_at=later,
    )
    assert updated == expected
    assert await repo.get_owned(note.id, owner) == expected


async def test_distinct_field_updates_preserve_both_and_same_field_last_write_wins():
    repo, owner = FakeNoteRepository(), uuid4()
    note = make_note(owner)
    await repo.add(note)
    await asyncio.gather(
        repo.update_owned(note.id, owner, NotePatch(title="first"), note.updated_at),
        repo.update_owned(note.id, owner, NotePatch(body="new body"), note.updated_at),
    )
    assert await repo.get_owned(note.id, owner) == replace(note, title="first", body="new body")
    await repo.update_owned(note.id, owner, NotePatch(title="last"), note.updated_at)
    assert (await repo.get_owned(note.id, owner)).title == "last"


async def test_failed_writes_leave_all_state_intact():
    repo, owner = FakeNoteRepository(), uuid4()
    note = make_note(owner)
    await repo.add(note)
    repo.fail_writes = True
    for operation in (
        repo.add(make_note(owner, 2)),
        repo.update_owned(note.id, owner, NotePatch(title="new", body="new"), note.updated_at),
        repo.delete_owned(note.id, owner),
    ):
        with pytest.raises(DependencyUnavailable):
            await operation
    assert await repo.list_by_owner(owner) == [note]


async def test_duplicate_identity_and_read_outages():
    repo, owner = FakeNoteRepository(), uuid4()
    note = make_note(owner)
    await repo.add(note)
    with pytest.raises(DependencyUnavailable):
        await repo.add(replace(note, title="overwrite"))
    assert await repo.get_owned(note.id, owner) == note
    repo.fail_reads = True
    for operation in (repo.list_by_owner(owner), repo.get_owned(note.id, owner)):
        with pytest.raises(DependencyUnavailable):
            await operation


async def test_only_one_delete_succeeds_and_later_patch_cannot_recreate():
    repo, owner = FakeNoteRepository(), uuid4()
    note = make_note(owner)
    await repo.add(note)
    removed = await asyncio.gather(
        repo.delete_owned(note.id, owner), repo.delete_owned(note.id, owner)
    )
    assert sorted(removed) == [False, True]
    assert await repo.update_owned(note.id, owner, NotePatch(body="new"), note.updated_at) is None
    assert await repo.get_owned(note.id, owner) is None
    assert await repo.list_by_owner(owner) == []
