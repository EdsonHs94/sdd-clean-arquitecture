"""Account registration HTTP boundary."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.dto import UserProfile
from app.application.use_cases.get_current_user import GetCurrentUser
from app.application.use_cases.register_user import RegisterUser
from app.domain.entities import User
from app.presentation.dependencies import get_authenticated_user, get_register_user
from app.presentation.schemas import RegistrationRequest, UserProfileResponse

router = APIRouter()


@router.post("/users", status_code=201, response_model=UserProfileResponse)
async def register_user(
    body: RegistrationRequest,
    use_case: Annotated[RegisterUser, Depends(get_register_user)],
) -> UserProfile:
    return await use_case.execute(body.name, body.email, body.password.get_secret_value())


@router.get("/me", response_model=UserProfileResponse)
async def current_user(user: Annotated[User, Depends(get_authenticated_user)]) -> UserProfile:
    return GetCurrentUser().execute(user)
