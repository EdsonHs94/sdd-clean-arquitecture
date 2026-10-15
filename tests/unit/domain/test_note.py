from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.domain import entities, errors


def make_note(**changes):
    values = dict(
        id=UUID(int=1),
        user_id=UUID(int=2),
        title="  Shopping  ",
        body="  bread\n ",
        created_at=datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=2))),
        updated_at=datetime(2026, 1, 1, 13, tzinfo=timezone(timedelta(hours=2))),
    )
    return entities.Note(**(values | changes))


def test_note_normalizes_title_and_dates_preserving_body():
    note = make_note()
    assert note.title == "Shopping"
    assert note.body == "  bread\n "
    assert note.created_at == datetime(2026, 1, 1, 10, tzinfo=UTC)
    assert note.updated_at == datetime(2026, 1, 1, 11, tzinfo=UTC)
    assert note.created_at.tzinfo is UTC
    assert note.updated_at.tzinfo is UTC


@pytest.mark.parametrize("title", ["x", "x" * 200, "  " + "x" * 200 + "  "])
def test_note_accepts_title_boundaries(title):
    assert make_note(title=title).title == title.strip()


@pytest.mark.parametrize("body", ["", "x" * 10_000, " \n\t ", "🙂" * 10_000])
def test_note_preserves_valid_body(body):
    assert make_note(body=body).body == body


@pytest.mark.parametrize("title", ["", " \t\n", "x" * 201, None, 1, True, []])
def test_note_rejects_invalid_title(title):
    with pytest.raises(errors.InvalidNoteData):
        make_note(title=title)


@pytest.mark.parametrize("body", ["x" * 10_001, None, 1, True, []])
def test_note_rejects_invalid_body(body):
    with pytest.raises(errors.InvalidNoteData):
        make_note(body=body)


@pytest.mark.parametrize("field", ["id", "user_id"])
def test_note_rejects_non_uuid_identity(field):
    with pytest.raises(errors.InvalidNoteData):
        make_note(**{field: "bad-id"})


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
@pytest.mark.parametrize("value", [None, "yesterday", datetime(2026, 1, 1)])
def test_note_rejects_invalid_or_naive_dates(field, value):
    with pytest.raises(errors.InvalidNoteData):
        make_note(**{field: value})


def test_note_is_immutable_and_does_not_expose_owner_or_body_in_repr():
    note = make_note(body="private note body")
    with pytest.raises(FrozenInstanceError):
        note.title = "other"
    assert str(note.user_id) not in repr(note)
    assert "private note body" not in repr(note)
