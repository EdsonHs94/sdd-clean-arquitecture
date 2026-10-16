"""Test-only stateful dependencies; never import these into production."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from app.application.dto import NotePatch, TokenResult
from app.application.errors import DependencyUnavailable, EmailAlreadyRegistered, NotAuthenticated
from app.domain.entities import File, Note, User


def _fake_password_hash(password: str) -> str:
    return "fake-sha256:" + sha256(password.encode()).hexdigest()


@dataclass
class FakeUserRepository:
    fail_reads: bool = False
    fail_writes: bool = False
    _users: dict[UUID, User] = field(default_factory=dict, init=False, repr=False)

    async def get_by_email(self, email: str) -> User | None:
        if self.fail_reads:
            raise DependencyUnavailable()
        return next((user for user in self._users.values() if user.email == email), None)

    async def get_by_id(self, user_id: UUID) -> User | None:
        if self.fail_reads:
            raise DependencyUnavailable()
        return self._users.get(user_id)

    async def add(self, user: User) -> None:
        if self.fail_writes:
            raise DependencyUnavailable()
        if any(existing.email == user.email for existing in self._users.values()):
            raise EmailAlreadyRegistered()
        if user.id in self._users:
            raise DependencyUnavailable()
        self._users[user.id] = user


@dataclass
class FakePasswordHasher:
    """Deterministic unsalted test hash; unsuitable for production credentials."""

    fail_hashing: bool = False
    fail_verification: bool = False

    async def hash(self, password: str) -> str:
        if self.fail_hashing:
            raise DependencyUnavailable()
        return _fake_password_hash(password)

    async def verify(self, password: str, password_hash: str) -> bool:
        if self.fail_verification:
            raise DependencyUnavailable()
        return password_hash == _fake_password_hash(password)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class FakeTokenService:
    """Opaque test tokens with controllable time; no JWT cryptography is performed."""

    clock: Callable[[], datetime] = field(default=_utc_now, repr=False)
    fail_issue: bool = False
    fail_verify: bool = False
    _tokens: dict[str, tuple[UUID, datetime]] = field(default_factory=dict, init=False, repr=False)

    async def issue(self, user_id: UUID) -> TokenResult:
        if self.fail_issue:
            raise DependencyUnavailable()
        token = f"fake-token-{len(self._tokens) + 1}"
        self._tokens[token] = (user_id, self.clock() + timedelta(seconds=3600))
        return TokenResult(access_token=token, expires_in=3600)

    async def verify(self, token: str) -> UUID:
        if self.fail_verify:
            raise DependencyUnavailable()
        record = self._tokens.get(token)
        if record is None or self.clock() >= record[1]:
            raise NotAuthenticated()
        return record[0]


@dataclass
class FakeFileRepository:
    fail_reads: bool = False
    fail_writes: bool = False
    _files: dict[UUID, File] = field(default_factory=dict, init=False, repr=False)

    async def add(self, file: File) -> None:
        if (
            self.fail_writes
            or file.id in self._files
            or any(existing.storage_key == file.storage_key for existing in self._files.values())
        ):
            raise DependencyUnavailable()
        self._files[file.id] = file

    async def list_by_owner(self, user_id: UUID) -> list[File]:
        if self.fail_reads:
            raise DependencyUnavailable()
        return sorted(
            (file for file in self._files.values() if file.user_id == user_id),
            key=lambda file: (file.created_at, file.id),
        )

    async def get_owned(self, file_id: UUID, user_id: UUID) -> File | None:
        if self.fail_reads:
            raise DependencyUnavailable()
        file = self._files.get(file_id)
        return file if file is not None and file.user_id == user_id else None

    async def delete_owned(self, file_id: UUID, user_id: UUID) -> bool:
        if self.fail_writes:
            raise DependencyUnavailable()
        file = self._files.get(file_id)
        if file is None or file.user_id != user_id:
            return False
        del self._files[file_id]
        return True


@dataclass
class FakeFileStorage:
    fail_upload: bool = False
    fail_delete: bool = False
    objects: dict[str, tuple[bytes, str]] = field(default_factory=dict, init=False, repr=False)
    calls: list[tuple[str, str]] = field(default_factory=list, init=False, repr=False)

    async def upload(self, key: str, content: bytes, content_type: str) -> None:
        self.calls.append(("upload", key))
        if self.fail_upload:
            raise DependencyUnavailable()
        self.objects[key] = (content, content_type)

    async def delete(self, key: str) -> None:
        self.calls.append(("delete", key))
        if self.fail_delete:
            raise DependencyUnavailable()
        self.objects.pop(key, None)


def make_file(owner, number=1, time=None):
    return File(
        UUID(int=number),
        owner,
        "sample.txt",
        f"files/{number}",
        "text/plain",
        3,
        time or datetime(2026, 1, 1, tzinfo=UTC),
    )


@dataclass
class FakeNoteRepository:
    fail_reads: bool = False
    fail_writes: bool = False
    _notes: dict[UUID, Note] = field(default_factory=dict, init=False, repr=False)

    async def add(self, note: Note) -> None:
        if self.fail_writes or note.id in self._notes:
            raise DependencyUnavailable()
        self._notes[note.id] = note

    async def list_by_owner(self, user_id: UUID) -> list[Note]:
        if self.fail_reads:
            raise DependencyUnavailable()
        return sorted(
            (note for note in self._notes.values() if note.user_id == user_id),
            key=lambda note: (note.created_at, note.id),
        )

    async def get_owned(self, note_id: UUID, user_id: UUID) -> Note | None:
        if self.fail_reads:
            raise DependencyUnavailable()
        note = self._notes.get(note_id)
        return note if note is not None and note.user_id == user_id else None

    async def update_owned(
        self, note_id: UUID, user_id: UUID, changes: NotePatch, updated_at: datetime
    ) -> Note | None:
        if self.fail_writes:
            raise DependencyUnavailable()
        note = self._notes.get(note_id)
        if note is None or note.user_id != user_id:
            return None
        updated = replace(
            note,
            title=changes.title if changes.title is not None else note.title,
            body=changes.body if changes.body is not None else note.body,
            updated_at=updated_at,
        )
        self._notes[note_id] = updated
        return updated

    async def delete_owned(self, note_id: UUID, user_id: UUID) -> bool:
        if self.fail_writes:
            raise DependencyUnavailable()
        note = self._notes.get(note_id)
        if note is None or note.user_id != user_id:
            return False
        del self._notes[note_id]
        return True


def make_note(owner, number=1, time=None):
    time = time or datetime(2026, 1, 1, tzinfo=UTC)
    return Note(UUID(int=number), owner, "Sample", " original body\n", time, time)
