"""Delete a private note after the repository confirms its removal."""

from uuid import UUID

from app.application.errors import NoteNotFound
from app.application.ports import NoteRepository


class DeleteUserNote:
    def __init__(self, repository: NoteRepository) -> None:
        self._repository = repository

    async def execute(self, user_id: UUID, note_id: UUID) -> None:
        if not await self._repository.delete_owned(note_id, user_id):
            raise NoteNotFound()
