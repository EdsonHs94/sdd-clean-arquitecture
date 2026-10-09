"""Credential login HTTP boundary."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.use_cases.login_user import LoginUser
from app.presentation.dependencies import get_login_user
from app.presentation.schemas import LoginRequest, TokenResponse

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
async def login_user(
    body: LoginRequest,
    use_case: Annotated[LoginUser, Depends(get_login_user)],
) -> TokenResponse:
    result = await use_case.execute(body.email, body.password.get_secret_value())
    return TokenResponse(access_token=result.access_token, expires_in=result.expires_in)
