from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.entities import File
from app.domain.errors import FileTooLarge, InvalidFileData
from app.domain.validation import (
    MAX_FILE_SIZE,
    normalize_content_type,
    validate_file_size,
    validate_filename,
)


@pytest.mark.parametrize("filename", ["a", "a" * 255, "photo.png", " a.txt ", "résumé.pdf"])
def test_valid_filename_is_preserved(filename):
    assert validate_filename(filename) == filename


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "a" * 256,
        "dir/file",
        "dir\\file",
        "a\x00b",
        "a\nb",
        "a\rb",
        "a\tb",
        "a\x7fb",
        "a\x85b",
        None,
        123,
    ],
)
def test_invalid_filename_is_rejected_without_echoing_input(filename):
    with pytest.raises(InvalidFileData) as error:
        validate_filename(filename)
    if isinstance(filename, str) and filename:
        assert filename not in str(error.value)


@pytest.mark.parametrize("size", [0, 1, MAX_FILE_SIZE])
def test_valid_sizes_include_zero_and_exact_limit(size):
    assert MAX_FILE_SIZE == 10_485_760
    assert validate_file_size(size) == size


def test_oversized_content_has_distinct_error():
    with pytest.raises(FileTooLarge, match="File too large"):
        validate_file_size(MAX_FILE_SIZE + 1)


@pytest.mark.parametrize("size", [-1, None, "10", 1.5, True])
def test_invalid_size_type_or_negative_size_is_rejected(size):
    with pytest.raises(InvalidFileData):
        validate_file_size(size)


@pytest.mark.parametrize(
    ("content_type", "expected"),
    [
        (None, "application/octet-stream"),
        ("", "application/octet-stream"),
        ("text/plain", "text/plain"),
        ("custom/file-type", "custom/file-type"),
    ],
)
def test_content_type_accepts_arbitrary_strings_and_defaults_when_absent(content_type, expected):
    assert normalize_content_type(content_type) == expected


def test_invalid_content_type_is_rejected():
    with pytest.raises(InvalidFileData):
        normalize_content_type(123)


@pytest.fixture
def fields():
    return dict(
        id=uuid4(),
        user_id=uuid4(),
        original_name="file.txt",
        storage_key="private-storage-locator",
        content_type=None,
        size=0,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_file_keeps_ownership_identity_and_separate_private_storage_key(fields):
    file = File(**fields)
    assert file.id == fields["id"]
    assert file.user_id == fields["user_id"]
    assert file.original_name == "file.txt"
    assert file.storage_key == fields["storage_key"]
    assert file.content_type == "application/octet-stream"
    assert file.size == 0
    assert file.created_at == fields["created_at"]
    assert fields["storage_key"] not in repr(file)
    assert fields["storage_key"] not in str(file)
    assert str(fields["user_id"]) not in repr(file)


def test_file_converts_aware_timestamp_to_utc(fields):
    file = File(
        **{**fields, "created_at": datetime(2026, 1, 1, 2, tzinfo=timezone(timedelta(hours=2)))}
    )
    assert file.created_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert file.created_at.tzinfo is UTC


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "invalid"},
        {"user_id": "invalid"},
        {"created_at": datetime(2026, 1, 1)},
        {"created_at": None},
        {"original_name": "folder/file"},
        {"size": -1},
        {"storage_key": ""},
        {"storage_key": None},
    ],
)
def test_file_enforces_invariants_at_construction(fields, changes):
    with pytest.raises(InvalidFileData):
        File(**{**fields, **changes})


def test_file_enforces_size_limit_at_construction(fields):
    with pytest.raises(FileTooLarge):
        File(**{**fields, "size": MAX_FILE_SIZE + 1})
