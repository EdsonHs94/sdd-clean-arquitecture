"""Retrieve safe owned metadata with indistinguishable missing/foreign failures."""

from uuid import UUID

from app.application.dto import FileMetadata
from app.application.errors import FileNotFound
from app.application.ports import FileRepository


class GetUserFile:
    def __init__(self, repository: FileRepository) -> None:
        self._repository = repository

    async def execute(self, user_id: UUID, file_id: UUID) -> FileMetadata:
        file = await self._repository.get_owned(file_id, user_id)
        if file is None:
            raise FileNotFound()
        return FileMetadata.from_file(file)
