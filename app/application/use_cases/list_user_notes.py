"""List private notes for the authenticated owner."""

from uuid import UUID

from app.application.dto import NoteResult
from app.application.ports import NoteRepository


class ListUserNotes:
    def __init__(self, repository: NoteRepository) -> None:
        self._repository = repository

    async def execute(self, user_id: UUID) -> list[NoteResult]:
        notes = await self._repository.list_by_owner(user_id)
        return [NoteResult.from_note(note) for note in notes]
