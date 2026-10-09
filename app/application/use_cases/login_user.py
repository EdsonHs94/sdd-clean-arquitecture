"""Authenticate credentials and issue an access token."""

from app.application.dto import TokenResult
from app.application.errors import InvalidCredentials
from app.application.ports import PasswordHasher, TokenService, UserRepository
from app.domain.validation import normalize_email, validate_password


class LoginUser:
    def __init__(
        self,
        repository: UserRepository,
        hasher: PasswordHasher,
        token_service: TokenService,
        *,
        dummy_password_hash: str,
    ) -> None:
        self._repository = repository
        self._hasher = hasher
        self._token_service = token_service
        self._dummy_password_hash = dummy_password_hash

    async def execute(self, email: str, password: str) -> TokenResult:
        email = normalize_email(email)
        password = validate_password(password)
        user = await self._repository.get_by_email(email)
        password_hash = user.password_hash if user is not None else self._dummy_password_hash
        valid = await self._hasher.verify(password, password_hash)
        if user is None or not valid:
            raise InvalidCredentials()
        return await self._token_service.issue(user.id)
