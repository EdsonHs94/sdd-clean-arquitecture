"""Upload private content, committing metadata or compensating persistence failure."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.application.dto import FileMetadata
from app.application.errors import DependencyUnavailable
from app.application.ports import FileRepository, FileStorage
from app.domain.entities import File

logger = logging.getLogger(__name__)


class UploadFile:
    def __init__(
        self,
        repository: FileRepository,
        storage: FileStorage,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._clock = clock
        self._id_factory = id_factory

    async def execute(
        self, user_id: UUID, filename: str, content: bytes, content_type: str | None = None
    ) -> FileMetadata:
        file_id = self._id_factory()
        file = File(
            id=file_id,
            user_id=user_id,
            original_name=filename,
            storage_key=f"files/{file_id}",
            content_type=content_type,
            size=len(content),
            created_at=self._clock(),
        )
        await self._storage.upload(file.storage_key, content, file.content_type)
        try:
            await self._repository.add(file)
        except DependencyUnavailable:
            try:
                await self._storage.delete(file.storage_key)
            except DependencyUnavailable:
                logger.warning(
                    "Upload cleanup failed for file ID %s; manual cleanup required", file.id
                )
            raise
        return FileMetadata.from_file(file)
