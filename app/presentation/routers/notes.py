"""Authenticated private note routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.application.use_cases.create_note import CreateNote
from app.application.use_cases.delete_user_note import DeleteUserNote
from app.application.use_cases.get_user_note import GetUserNote
from app.application.use_cases.list_user_notes import ListUserNotes
from app.application.use_cases.update_user_note import UpdateUserNote
from app.domain.entities import User
from app.presentation.dependencies import (
    get_authenticated_user,
    get_create_note,
    get_delete_user_note,
    get_list_user_notes,
    get_update_user_note,
    get_user_note,
)
from app.presentation.schemas import NoteCreateRequest, NoteResponse, NoteUpdateRequest

router = APIRouter()


@router.post("/notes", status_code=201, response_model=NoteResponse)
async def create_note(
    body: NoteCreateRequest,
    user: Annotated[User, Depends(get_authenticated_user)],
    use_case: Annotated[CreateNote, Depends(get_create_note)],
) -> NoteResponse:
    result = await use_case.execute(user.id, body.title, body.body)
    return NoteResponse.model_validate(result)


@router.get("/notes", response_model=list[NoteResponse])
async def list_notes(
    user: Annotated[User, Depends(get_authenticated_user)],
    use_case: Annotated[ListUserNotes, Depends(get_list_user_notes)],
) -> list[NoteResponse]:
    results = await use_case.execute(user.id)
    return [NoteResponse.model_validate(result) for result in results]


@router.get("/notes/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: UUID,
    user: Annotated[User, Depends(get_authenticated_user)],
    use_case: Annotated[GetUserNote, Depends(get_user_note)],
) -> NoteResponse:
    result = await use_case.execute(user.id, note_id)
    return NoteResponse.model_validate(result)


@router.patch("/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: UUID,
    body: NoteUpdateRequest,
    user: Annotated[User, Depends(get_authenticated_user)],
    use_case: Annotated[UpdateUserNote, Depends(get_update_user_note)],
) -> NoteResponse:
    result = await use_case.execute(user.id, note_id, title=body.title, body=body.body)
    return NoteResponse.model_validate(result)


@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(
    note_id: UUID,
    user: Annotated[User, Depends(get_authenticated_user)],
    use_case: Annotated[DeleteUserNote, Depends(get_delete_user_note)],
) -> Response:
    await use_case.execute(user.id, note_id)
    return Response(status_code=204)
