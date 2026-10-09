from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

from app.application.use_cases.get_current_user import GetCurrentUser
from app.domain.entities import User


def test_current_profile_uses_only_resolved_user_and_omits_hash(caplog):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    user = User(
        id=uuid4(),
        name="Alice",
        email="alice@example.com",
        password_hash="private-hash",
        created_at=now,
    )
    profile = GetCurrentUser().execute(user)
    assert asdict(profile) == {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "created_at": now,
    }
    assert "private-hash" not in repr(profile)
    assert "private-hash" not in caplog.text


def test_two_authenticated_users_receive_distinct_profiles():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    alice = User(
        id=uuid4(),
        name="Alice",
        email="alice@example.com",
        password_hash="alice-hash",
        created_at=now,
    )
    bob = User(
        id=uuid4(), name="Bob", email="bob@example.com", password_hash="bob-hash", created_at=now
    )
    current = GetCurrentUser()
    assert current.execute(alice).id == alice.id
    assert current.execute(bob).id == bob.id
    assert current.execute(alice) != current.execute(bob)
