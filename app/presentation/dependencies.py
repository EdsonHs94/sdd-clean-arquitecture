"""FastAPI dependency wiring, kept outside application logic."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.errors import NotAuthenticated
from app.application.ports import (
    FileRepository,
    FileStorage,
    PasswordHasher,
    TokenService,
    UserRepository,
)
from app.application.use_cases.authenticate_user import AuthenticateUser
from app.application.use_cases.delete_user_file import DeleteUserFile
from app.application.use_cases.get_user_file import GetUserFile
from app.application.use_cases.list_user_files import ListUserFiles
from app.application.use_cases.login_user import LoginUser
from app.application.use_cases.register_user import RegisterUser
from app.application.use_cases.upload_file import UploadFile
from app.domain.entities import User

bearer = HTTPBearer(auto_error=False)


async def get_user_repository(request: Request) -> AsyncIterator[UserRepository]:
    async with request.app.state.database.session() as session:
        # The root installs this factory; transport does not construct an adapter.
        yield request.app.state.user_repository_factory(session)


def get_password_hasher(request: Request) -> PasswordHasher:
    return request.app.state.password_hasher


def get_token_service(request: Request) -> TokenService:
    return request.app.state.token_service


def get_register_user(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
) -> RegisterUser:
    return RegisterUser(repository, hasher)


def get_login_user(
    request: Request,
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> LoginUser:
    return LoginUser(
        repository, hasher, tokens, dummy_password_hash=request.app.state.dummy_password_hash
    )


async def get_authenticated_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> User:
    if credentials is None:
        raise NotAuthenticated()
    return await AuthenticateUser(repository, tokens).execute(credentials.credentials)


async def get_file_repository(request: Request) -> AsyncIterator[FileRepository]:
    async with request.app.state.database.session() as session:
        yield request.app.state.file_repository_factory(session)


def get_file_storage(request: Request) -> FileStorage:
    return request.app.state.file_storage


def get_upload_file(
    repository: Annotated[FileRepository, Depends(get_file_repository)],
    storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> UploadFile:
    return UploadFile(repository, storage)


def get_list_user_files(
    repository: Annotated[FileRepository, Depends(get_file_repository)],
) -> ListUserFiles:
    return ListUserFiles(repository)


def get_user_file(
    repository: Annotated[FileRepository, Depends(get_file_repository)],
) -> GetUserFile:
    return GetUserFile(repository)


def get_delete_user_file(
    repository: Annotated[FileRepository, Depends(get_file_repository)],
    storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> DeleteUserFile:
    return DeleteUserFile(repository, storage)
