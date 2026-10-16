"""Committed owner-scoped notes with atomic updates of only supplied fields."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto import NotePatch
from app.application.errors import DependencyUnavailable
from app.domain.entities import Note
from app.infrastructure.persistence.models import NoteModel


def _to_domain(model: NoteModel) -> Note:
    return Note(
        id=model.id,
        user_id=model.user_id,
        title=model.title,
        body=model.body,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyNoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _rollback(self) -> None:
        try:
            await self._session.rollback()
        except (SQLAlchemyError, OSError):
            raise DependencyUnavailable() from None

    async def add(self, note: Note) -> None:
        try:
            self._session.add(
                NoteModel(
                    id=note.id,
                    user_id=note.user_id,
                    title=note.title,
                    body=note.body,
                    created_at=note.created_at,
                    updated_at=note.updated_at,
                )
            )
            await self._session.commit()
        except (SQLAlchemyError, OSError):
            await self._rollback()
            raise DependencyUnavailable() from None

    async def list_by_owner(self, user_id: UUID) -> list[Note]:
        try:
            result = await self._session.execute(
                select(NoteModel)
                .where(NoteModel.user_id == user_id)
                .order_by(NoteModel.created_at, NoteModel.id)
            )
            return [_to_domain(model) for model in result.scalars()]
        except (SQLAlchemyError, OSError):
            raise DependencyUnavailable() from None

    async def get_owned(self, note_id: UUID, user_id: UUID) -> Note | None:
        try:
            result = await self._session.execute(
                select(NoteModel).where(NoteModel.id == note_id, NoteModel.user_id == user_id)
            )
            model = result.scalar_one_or_none()
            return _to_domain(model) if model is not None else None
        except (SQLAlchemyError, OSError):
            raise DependencyUnavailable() from None

    async def update_owned(
        self, note_id: UUID, user_id: UUID, changes: NotePatch, updated_at: datetime
    ) -> Note | None:
        values: dict[str, str | datetime] = {"updated_at": updated_at}
        if changes.title is not None:
            values["title"] = changes.title
        if changes.body is not None:
            values["body"] = changes.body
        try:
            result = await self._session.execute(
                update(NoteModel)
                .where(NoteModel.id == note_id, NoteModel.user_id == user_id)
                .values(**values)
                .returning(NoteModel)
                .execution_options(populate_existing=True)
            )
            model = result.scalar_one_or_none()
            # Copy before commit so the result also works with expiring sessions.
            note = _to_domain(model) if model is not None else None
            await self._session.commit()
            return note
        except (SQLAlchemyError, OSError):
            await self._rollback()
            raise DependencyUnavailable() from None

    async def delete_owned(self, note_id: UUID, user_id: UUID) -> bool:
        try:
            result = await self._session.execute(
                delete(NoteModel)
                .where(NoteModel.id == note_id, NoteModel.user_id == user_id)
                .returning(NoteModel.id)
            )
            removed = result.scalar_one_or_none() is not None
            await self._session.commit()
            return removed
        except (SQLAlchemyError, OSError):
            await self._rollback()
            raise DependencyUnavailable() from None
