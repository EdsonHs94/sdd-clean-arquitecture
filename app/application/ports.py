"""External capabilities required by the application."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.dto import NotePatch, TokenResult
from app.domain.entities import File, Note, User


class NoteRepository(Protocol):
    """Owner-scoped persistence; writes commit before return or roll back on failure.

    Operational failures raise DependencyUnavailable. Missing and foreign rows are
    indistinguishable. Update changes only present fields and updated_at, preserving
    concurrent edits to omitted fields; None denotes an absent owned row.
    """

    async def add(self, note: Note) -> None: ...

    async def list_by_owner(self, user_id: UUID) -> list[Note]: ...

    async def get_owned(self, note_id: UUID, user_id: UUID) -> Note | None: ...

    async def update_owned(
        self, note_id: UUID, user_id: UUID, changes: NotePatch, updated_at: datetime
    ) -> Note | None: ...

    async def delete_owned(self, note_id: UUID, user_id: UUID) -> bool: ...


class UserRepository(Protocol):
    """Adds commit before returning; duplicate email and outages are distinct errors."""

    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def add(self, user: User) -> None: ...


class PasswordHasher(Protocol):
    """Hash/verify credentials; operational failures raise DependencyUnavailable."""

    async def hash(self, password: str) -> str: ...

    async def verify(self, password: str, password_hash: str) -> bool: ...


class TokenService(Protocol):
    """Verify returns a UUID; invalid tokens and dependency outages are distinct."""

    async def issue(self, user_id: UUID) -> TokenResult: ...

    async def verify(self, token: str) -> UUID: ...


class FileRepository(Protocol):
    """Owner-scoped reads; mutations commit before returning or roll back on failure.

    Operational failures raise DependencyUnavailable. Delete returns whether an
    owned row was removed, including False after a concurrent deletion.
    """

    async def add(self, file: File) -> None: ...

    async def list_by_owner(self, user_id: UUID) -> list[File]: ...

    async def get_owned(self, file_id: UUID, user_id: UUID) -> File | None: ...

    async def delete_owned(self, file_id: UUID, user_id: UUID) -> bool: ...


class FileStorage(Protocol):
    """Private object writes; operational failures raise DependencyUnavailable.

    Delete succeeds when an object is already absent. Keys are opaque application
    locators, independent of client filenames. No public reads or URLs are exposed.
    """

    async def upload(self, key: str, content: bytes, content_type: str) -> None: ...

    async def delete(self, key: str) -> None: ...
