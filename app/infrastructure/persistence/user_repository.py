"""User repository backed by SQLAlchemy; ORM types never leave this adapter."""

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.errors import DependencyUnavailable, EmailAlreadyRegistered
from app.domain.entities import User
from app.infrastructure.persistence.models import UserModel


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        name=model.name,
        password_hash=model.password_hash,
        created_at=model.created_at,
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        return await self._get(select(UserModel).where(UserModel.email == email))

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self._get(select(UserModel).where(UserModel.id == user_id))

    async def _get(self, statement: Select[tuple[UserModel]]) -> User | None:
        try:
            result = await self._session.execute(statement)
            model = result.scalar_one_or_none()
            return _to_domain(model) if model is not None else None
        except (SQLAlchemyError, OSError):
            raise DependencyUnavailable() from None

    async def _rollback(self) -> None:
        try:
            await self._session.rollback()
        except (SQLAlchemyError, OSError):
            raise DependencyUnavailable() from None

    async def add(self, user: User) -> None:
        model = UserModel(
            id=user.id,
            email=user.email,
            name=user.name,
            password_hash=user.password_hash,
            created_at=user.created_at,
        )
        try:
            self._session.add(model)
            await self._session.commit()
        except IntegrityError as error:
            constraint = getattr(error.orig.__cause__, "constraint_name", None)
            duplicate_email = (
                getattr(error.orig, "sqlstate", None) == "23505" and constraint == "uq_users_email"
            )
            await self._rollback()
            if duplicate_email:
                raise EmailAlreadyRegistered() from None
            raise DependencyUnavailable() from None
        except (SQLAlchemyError, OSError):
            await self._rollback()
            raise DependencyUnavailable() from None
