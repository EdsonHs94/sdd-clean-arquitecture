"""Apply only supplied fields through the atomic owner-scoped update port."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from app.application.dto import NotePatch, NoteResult
from app.application.errors import NoteNotFound
from app.application.ports import NoteRepository


class UpdateUserNote:
    def __init__(
        self,
        repository: NoteRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._clock = clock

    async def execute(
        self, user_id: UUID, note_id: UUID, *, title: str | None = None, body: str | None = None
    ) -> NoteResult:
        changes = NotePatch(title=title, body=body)
        note = await self._repository.update_owned(note_id, user_id, changes, self._clock())
        if note is None:
            raise NoteNotFound()
        return NoteResult.from_note(note)
