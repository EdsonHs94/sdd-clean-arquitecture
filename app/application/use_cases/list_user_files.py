"""List safe metadata for the authenticated owner."""

from uuid import UUID

from app.application.dto import FileMetadata
from app.application.ports import FileRepository


class ListUserFiles:
    def __init__(self, repository: FileRepository) -> None:
        self._repository = repository

    async def execute(self, user_id: UUID) -> list[FileMetadata]:
        files = await self._repository.list_by_owner(user_id)
        return [FileMetadata.from_file(file) for file in files]
