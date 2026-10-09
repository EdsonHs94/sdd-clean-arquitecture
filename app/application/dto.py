"""Plain application results without transport or vendor types."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities import File, User


@dataclass(frozen=True, slots=True)
class UserProfile:
    id: UUID
    name: str
    email: str
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserProfile":
        return cls(id=user.id, name=user.name, email=user.email, created_at=user.created_at)


@dataclass(frozen=True, slots=True)
class TokenResult:
    access_token: str = field(repr=False)
    expires_in: int


@dataclass(frozen=True, slots=True)
class FileMetadata:
    """Safe metadata; excludes owner identity and the private storage locator."""

    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime

    @classmethod
    def from_file(cls, file: File) -> "FileMetadata":
        return cls(
            id=file.id,
            filename=file.original_name,
            content_type=file.content_type,
            size_bytes=file.size,
            created_at=file.created_at,
        )
