"""Create a private note using server-generated identity and timestamps."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.application.dto import NoteResult
from app.application.ports import NoteRepository
from app.domain.entities import Note
from app.domain.validation import validate_note_body, validate_note_title


class CreateNote:
    def __init__(
        self,
        repository: NoteRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._id_factory = id_factory

    async def execute(self, user_id: UUID, title: str, body: str) -> NoteResult:
        title = validate_note_title(title)
        body = validate_note_body(body)
        now = self._clock()
        note = Note(self._id_factory(), user_id, title, body, now, now)
        await self._repository.add(note)
        return NoteResult.from_note(note)
