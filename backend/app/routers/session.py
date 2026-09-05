from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_workspace_key
from app.repositories import (
    MessageRepository,
    QueryRecordRepository,
    SessionRepository,
    WorkspaceRepository,
)
from app.schemas import SessionCreate, SessionListResponse, SessionResponse, SessionUpdate
from app.services import SessionService

router = APIRouter(prefix="/session", tags=["session"])


def get_session_service(db: Session = Depends(get_db)) -> SessionService:
    repository = SessionRepository(db)
    workspace_repository = WorkspaceRepository(db)
    query_record_repository = QueryRecordRepository(db)
    message_repository = MessageRepository(db)
    return SessionService(
        repository, workspace_repository, query_record_repository, message_repository
    )


@router.post("/", response_model=SessionResponse)
def create_session(
    payload: SessionCreate,
    workspace_key: str = Depends(get_workspace_key),
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    session = service.create_session(workspace_key, payload.name)
    return SessionResponse.model_validate(session)


@router.get("/", response_model=SessionListResponse)
def list_sessions(
    page: Annotated[int, Query(ge=1)] = 1,
    workspace_key: str = Depends(get_workspace_key),
    service: SessionService = Depends(get_session_service),
) -> SessionListResponse:
    return service.list_sessions(workspace_key, page)


@router.get("/{session_key}", response_model=SessionResponse)
def get_session(
    session_key: str,
    workspace_key: Annotated[str | None, Header(alias="X-Workspace-Key")] = None,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    session = service.get_session_by_key(workspace_key, session_key)
    messages = service.get_session_history(session.id)
    return SessionResponse(session_key=session.session_key, name=session.name, messages=messages)


@router.patch("/{session_key}", response_model=SessionResponse)
def update_session(
    session_key: str,
    payload: SessionUpdate,
    workspace_key: str = Depends(get_workspace_key),
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    session = service.update_session(workspace_key, session_key, payload.name)
    return SessionResponse.model_validate(session)
