from dataclasses import asdict

import pytest

from app.application import dto
from app.domain.errors import InvalidNoteData
from tests.unit.domain.test_note import make_note


def test_note_result_projects_only_public_fields():
    result = dto.NoteResult.from_note(make_note())
    assert set(asdict(result)) == {"id", "title", "body", "created_at", "updated_at"}
    assert result.title == "Shopping"
    assert result.body == "  bread\n "


def test_patch_distinguishes_empty_body_from_omission_and_normalizes_title():
    title = dto.NotePatch(title="  New title  ")
    assert title.title == "New title"
    assert title.body is None
    body = dto.NotePatch(body="")
    assert body.title is None
    assert body.body == ""


@pytest.mark.parametrize(
    "fields",
    [{}, {"title": " "}, {"body": "x" * 10_001}, {"title": "valid", "body": 1}],
    ids=["empty", "blank-title", "oversized-body", "partial-invalid"],
)
def test_patch_rejects_empty_and_invalid_changes(fields):
    with pytest.raises(InvalidNoteData):
        dto.NotePatch(**fields)
