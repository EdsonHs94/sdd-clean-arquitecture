"""Register a validated account."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.application.dto import UserProfile
from app.application.errors import EmailAlreadyRegistered
from app.application.ports import PasswordHasher, UserRepository
from app.domain.entities import User
from app.domain.validation import normalize_email, validate_name, validate_password


class RegisterUser:
    def __init__(
        self,
        repository: UserRepository,
        hasher: PasswordHasher,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._hasher = hasher
        self._clock = clock
        self._id_factory = id_factory

    async def execute(self, name: str, email: str, password: str) -> UserProfile:
        name = validate_name(name)
        email = normalize_email(email)
        password = validate_password(password)
        if await self._repository.get_by_email(email) is not None:
            raise EmailAlreadyRegistered()
        password_hash = await self._hasher.hash(password)
        user = User(
            id=self._id_factory(),
            name=name,
            email=email,
            password_hash=password_hash,
            created_at=self._clock(),
        )
        await self._repository.add(user)
        return UserProfile.from_user(user)
