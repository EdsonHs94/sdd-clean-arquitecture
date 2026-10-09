"""Delete owned content before committing metadata removal; partial failures permit retry."""

from uuid import UUID

from app.application.errors import FileNotFound
from app.application.ports import FileRepository, FileStorage


class DeleteUserFile:
    def __init__(self, repository: FileRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    async def execute(self, user_id: UUID, file_id: UUID) -> None:
        file = await self._repository.get_owned(file_id, user_id)
        if file is None:
            raise FileNotFound()
        await self._storage.delete(file.storage_key)
        if not await self._repository.delete_owned(file_id, user_id):
            raise FileNotFound()
