"""Argon2id password-hasher adapter."""

import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import HashingError, InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

from app.application.errors import DependencyUnavailable


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._hasher = PasswordHasher(type=Type.ID)

    async def hash(self, password: str) -> str:
        try:
            return await asyncio.to_thread(self._hasher.hash, password)
        except (HashingError, ValueError, TypeError):
            raise DependencyUnavailable() from None

    async def verify(self, password: str, password_hash: str) -> bool:
        try:
            return await asyncio.to_thread(self._hasher.verify, password_hash, password)
        except VerifyMismatchError:
            return False
        except (VerificationError, InvalidHashError, ValueError, TypeError):
            raise DependencyUnavailable() from None
