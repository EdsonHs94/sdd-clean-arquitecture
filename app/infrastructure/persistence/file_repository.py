"""Committed, owner-filtered file persistence; ORM objects stay inside this adapter."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.errors import DependencyUnavailable
from app.domain.entities import File
from app.infrastructure.persistence.models import FileModel


def _to_domain(model: FileModel) -> File:
    return File(
        id=model.id,
        user_id=model.user_id,
        original_name=model.original_name,
        storage_key=model.storage_key,
        content_type=model.content_type,
        size=model.size,
        created_at=model.created_at,
    )


class SqlAlchemyFileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _rollback(self) -> None:
        try:
            await self._session.rollback()
        except (SQLAlchemyError, OSError):
            raise DependencyUnavailable() from None

    async def add(self, file: File) -> None:
        try:
            self._session.add(
                FileModel(
                    id=file.id,
                    user_id=file.user_id,
                    original_name=file.original_name,
                    storage_key=file.storage_key,
                    content_type=file.content_type,
                    size=file.size,
                    created_at=file.created_at,
                )
            )
            await self._session.commit()
        except (SQLAlchemyError, OSError):
            await self._rollback()
            raise DependencyUnavailable() from None

    async def list_by_owner(self, user_id: UUID) -> list[File]:
        try:
            result = await self._session.execute(
                select(FileModel)
                .where(FileModel.user_id == user_id)
                .order_by(FileModel.created_at, FileModel.id)
            )
            return [_to_domain(model) for model in result.scalars()]
        except (SQLAlchemyError, OSError):
            raise DependencyUnavailable() from None

    async def get_owned(self, file_id: UUID, user_id: UUID) -> File | None:
        try:
            result = await self._session.execute(
                select(FileModel).where(FileModel.id == file_id, FileModel.user_id == user_id)
            )
            model = result.scalar_one_or_none()
            return _to_domain(model) if model is not None else None
        except (SQLAlchemyError, OSError):
            raise DependencyUnavailable() from None

    async def delete_owned(self, file_id: UUID, user_id: UUID) -> bool:
        try:
            result = await self._session.execute(
                delete(FileModel)
                .where(FileModel.id == file_id, FileModel.user_id == user_id)
                .returning(FileModel.id)
            )
            removed = result.scalar_one_or_none() is not None
            await self._session.commit()
            return removed
        except (SQLAlchemyError, OSError):
            await self._rollback()
            raise DependencyUnavailable() from None
