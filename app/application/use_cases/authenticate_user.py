"""Resolve an access token to an existing user."""

from uuid import UUID

from app.application.errors import NotAuthenticated
from app.application.ports import TokenService, UserRepository
from app.domain.entities import User


class AuthenticateUser:
    def __init__(self, repository: UserRepository, token_service: TokenService) -> None:
        self._repository = repository
        self._token_service = token_service

    async def execute(self, token: str) -> User:
        if not isinstance(token, str) or not token:
            raise NotAuthenticated()
        subject = await self._token_service.verify(token)
        if not isinstance(subject, UUID):
            raise NotAuthenticated()
        user = await self._repository.get_by_id(subject)
        if user is None:
            raise NotAuthenticated()
        return user
