"""Project an already authenticated user into a safe profile."""

from app.application.dto import UserProfile
from app.domain.entities import User


class GetCurrentUser:
    def execute(self, user: User) -> UserProfile:
        return UserProfile.from_user(user)
