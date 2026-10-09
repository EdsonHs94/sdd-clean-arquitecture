"""Authenticated file routes; ownership comes only from the resolved user."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.application.use_cases.delete_user_file import DeleteUserFile
from app.application.use_cases.get_user_file import GetUserFile
from app.application.use_cases.list_user_files import ListUserFiles
from app.application.use_cases.upload_file import UploadFile
from app.domain.entities import User
from app.presentation.dependencies import (
    get_authenticated_user,
    get_delete_user_file,
    get_list_user_files,
    get_upload_file,
    get_user_file,
)
from app.presentation.schemas import FileMetadataResponse
from app.presentation.uploads import read_upload

router = APIRouter()


@router.post("/files", status_code=201, response_model=FileMetadataResponse)
async def upload_file(
    request: Request,
    user: Annotated[User, Depends(get_authenticated_user)],
    use_case: Annotated[UploadFile, Depends(get_upload_file)],
) -> FileMetadataResponse:
    filename, content, content_type = await read_upload(request)
    result = await use_case.execute(user.id, filename, content, content_type)
    return FileMetadataResponse.model_validate(result)


@router.get("/files", response_model=list[FileMetadataResponse])
async def list_files(
    user: Annotated[User, Depends(get_authenticated_user)],
    use_case: Annotated[ListUserFiles, Depends(get_list_user_files)],
) -> list[FileMetadataResponse]:
    results = await use_case.execute(user.id)
    return [FileMetadataResponse.model_validate(result) for result in results]


@router.get("/files/{file_id}", response_model=FileMetadataResponse)
async def get_file(
    file_id: UUID,
    user: Annotated[User, Depends(get_authenticated_user)],
    use_case: Annotated[GetUserFile, Depends(get_user_file)],
) -> FileMetadataResponse:
    result = await use_case.execute(user.id, file_id)
    return FileMetadataResponse.model_validate(result)


@router.delete("/files/{file_id}", status_code=204)
async def delete_file(
    file_id: UUID,
    user: Annotated[User, Depends(get_authenticated_user)],
    use_case: Annotated[DeleteUserFile, Depends(get_delete_user_file)],
) -> Response:
    await use_case.execute(user.id, file_id)
    return Response(status_code=204)
