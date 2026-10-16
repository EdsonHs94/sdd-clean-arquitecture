"""Plain application results without transport or vendor types."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities import File, Note, User
from app.domain.errors import InvalidNoteData
from app.domain.validation import validate_note_body, validate_note_title


@dataclass(frozen=True, slots=True)
class NotePatch:
    """None denotes omission; HTTP must reject explicit null before conversion."""

    title: str | None = None
    body: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.title is None and self.body is None:
            raise InvalidNoteData("At least one note field is required")
        if self.title is not None:
            object.__setattr__(self, "title", validate_note_title(self.title))
        if self.body is not None:
            object.__setattr__(self, "body", validate_note_body(self.body))


@dataclass(frozen=True, slots=True)
class NoteResult:
    id: UUID
    title: str
    body: str = field(repr=False)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_note(cls, note: Note) -> "NoteResult":
        return cls(note.id, note.title, note.body, note.created_at, note.updated_at)


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
