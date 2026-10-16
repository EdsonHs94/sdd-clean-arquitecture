"""Retrieve a private note without exposing owner identity."""

from uuid import UUID

from app.application.dto import NoteResult
from app.application.errors import NoteNotFound
from app.application.ports import NoteRepository


class GetUserNote:
    def __init__(self, repository: NoteRepository) -> None:
        self._repository = repository

    async def execute(self, user_id: UUID, note_id: UUID) -> NoteResult:
        note = await self._repository.get_owned(note_id, user_id)
        if note is None:
            raise NoteNotFound()
        return NoteResult.from_note(note)
