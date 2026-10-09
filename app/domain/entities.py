"""Plain domain entities."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from app.domain.errors import InvalidFileData, InvalidUserData
from app.domain.validation import (
    normalize_content_type,
    normalize_email,
    validate_file_size,
    validate_filename,
    validate_name,
)


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    name: str
    email: str
    password_hash: str = field(repr=False)
    created_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise InvalidUserData("User ID must be a UUID")
        if not isinstance(self.created_at, datetime) or self.created_at.utcoffset() is None:
            raise InvalidUserData("Creation time must be timezone-aware")
        object.__setattr__(self, "name", validate_name(self.name))
        object.__setattr__(self, "email", normalize_email(self.email))
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class File:
    id: UUID
    user_id: UUID = field(repr=False)
    original_name: str
    storage_key: str = field(repr=False)
    content_type: str | None
    size: int
    created_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.user_id, UUID):
            raise InvalidFileData("File and owner IDs must be UUIDs")
        if not isinstance(self.storage_key, str) or not self.storage_key:
            raise InvalidFileData("Storage key must be nonempty")
        if not isinstance(self.created_at, datetime) or self.created_at.utcoffset() is None:
            raise InvalidFileData("Creation time must be timezone-aware")
        object.__setattr__(self, "original_name", validate_filename(self.original_name))
        object.__setattr__(self, "content_type", normalize_content_type(self.content_type))
        object.__setattr__(self, "size", validate_file_size(self.size))
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
