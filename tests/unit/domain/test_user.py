from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.entities import User
from app.domain.errors import InvalidUserData
from app.domain.validation import normalize_email, validate_name, validate_password


@pytest.mark.parametrize("name", ["a", "a" * 100, "  Alice  "])
def test_valid_name_is_trimmed(name):
    assert validate_name(name) == name.strip()


@pytest.mark.parametrize("name", ["", "   ", "a" * 101, None, 123])
def test_invalid_name_is_rejected(name):
    with pytest.raises(InvalidUserData):
        validate_name(name)


@pytest.mark.parametrize("password", ["a" * 8, "a" * 128, "  pass  ", " " * 8])
def test_password_length_is_validated_without_trimming(password):
    assert validate_password(password) == password


@pytest.mark.parametrize("password", ["a" * 7, "a" * 129, "", None, 123])
def test_invalid_password_errors_do_not_echo_input(password):
    with pytest.raises(InvalidUserData) as error:
        validate_password(password)
    if isinstance(password, str) and password:
        assert password not in str(error.value)


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        (" Alice@EXAMPLE.COM ", "alice@example.com"),
        ("Alice+Tag@example.com", "alice+tag@example.com"),
        ("first.last@example.org", "first.last@example.org"),
        (
            "a" * 64 + "@" + ".".join(["b" * 63, "b" * 63, "b" * 57, "com"]),
            "a" * 64 + "@" + ".".join(["b" * 63, "b" * 63, "b" * 57, "com"]),
        ),
    ],
)
def test_email_syntax_and_normalization(email, expected):
    assert normalize_email(email) == expected


@pytest.mark.parametrize(
    "email",
    [
        "",
        "no-at-sign",
        "a@",
        "@example.com",
        "a b@example.com",
        "a@localhost",
        "a..b@example.com",
        "a" * 65 + "@example.com",
        "a" * 64 + "@" + ".".join(["b" * 63, "b" * 63, "b" * 58, "com"]),
        None,
        123,
    ],
)
def test_invalid_email_is_rejected_without_echoing_input(email):
    with pytest.raises(InvalidUserData) as error:
        normalize_email(email)
    if isinstance(email, str) and email:
        assert email not in str(error.value)


def test_user_preserves_identity_and_hides_hash():
    user_id = uuid4()
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    user = User(
        id=user_id,
        name=" Alice ",
        email="Alice@EXAMPLE.COM",
        password_hash="sensitive-hash",
        created_at=created_at,
    )
    assert user.id == user_id
    assert user.name == "Alice"
    assert user.email == "alice@example.com"
    assert user.password_hash == "sensitive-hash"
    assert user.created_at == created_at
    assert "sensitive-hash" not in repr(user)
    assert "sensitive-hash" not in str(user)


def test_user_converts_aware_timestamp_to_utc():
    user = User(
        id=uuid4(),
        name="Alice",
        email="alice@example.com",
        password_hash="hash",
        created_at=datetime(2026, 1, 1, 2, tzinfo=timezone(timedelta(hours=2))),
    )
    assert user.created_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert user.created_at.tzinfo is UTC


@pytest.mark.parametrize(
    ("user_id", "created_at"),
    [("not-a-uuid", datetime(2026, 1, 1, tzinfo=UTC)), (uuid4(), datetime(2026, 1, 1))],
)
def test_user_rejects_invalid_identity_or_naive_timestamp(user_id, created_at):
    with pytest.raises(InvalidUserData):
        User(
            id=user_id,
            name="Alice",
            email="alice@example.com",
            password_hash="hash",
            created_at=created_at,
        )
