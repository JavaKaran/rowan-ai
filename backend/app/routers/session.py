from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.db import get_db
from app.exceptions import WorkspaceKeyMissing
from app.repositories import SessionRepository, WorkspaceRepository
from app.schemas import SessionCreate, SessionResponse, SessionUpdate
from app.services import SessionService

router = APIRouter(prefix="/session", tags=["session"])


def get_session_service(db: Session = Depends(get_db)) -> SessionService:
    repository = SessionRepository(db)
    workspace_repository = WorkspaceRepository(db)
    return SessionService(repository, workspace_repository)


def get_workspace_key(
    x_workspace_key: Annotated[str | None, Header(alias="X-Workspace-Key")] = None,
) -> str:
    if not x_workspace_key or not x_workspace_key.strip():
        raise WorkspaceKeyMissing()

    return x_workspace_key


@router.post("/", response_model=SessionResponse)
def create_session(
    payload: SessionCreate,
    workspace_key: str = Depends(get_workspace_key),
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    session = service.create_session(workspace_key, payload.name)
    return SessionResponse.model_validate(session)


@router.get("/{session_key}", response_model=SessionResponse)
def get_session(
    session_key: str,
    workspace_key: str = Depends(get_workspace_key),
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    session = service.get_session_by_key(workspace_key, session_key)
    return SessionResponse.model_validate(session)


@router.patch("/{session_key}", response_model=SessionResponse)
def update_session(
    session_key: str,
    payload: SessionUpdate,
    workspace_key: str = Depends(get_workspace_key),
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    session = service.update_session(workspace_key, session_key, payload.name)
    return SessionResponse.model_validate(session)
