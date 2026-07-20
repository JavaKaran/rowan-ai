from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import SessionRepository
from app.schemas import SessionCreate, SessionResponse, SessionUpdate
from app.services import SessionService

router = APIRouter(prefix="/session", tags=["session"])


def get_session_service(db: Session = Depends(get_db)) -> SessionService:
    repository = SessionRepository(db)
    return SessionService(repository)


@router.post("/", response_model=SessionResponse)
def create_session(
    payload: SessionCreate,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    session = service.create_session(payload.name)
    return SessionResponse.model_validate(session)


@router.get("/{session_key}", response_model=SessionResponse)
def get_session(
    session_key: str,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    session = service.get_session_by_key(session_key)
    return SessionResponse.model_validate(session)


@router.patch("/{session_key}", response_model=SessionResponse)
def update_session(
    session_key: str,
    payload: SessionUpdate,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    session = service.update_session(session_key, payload.name)
    return SessionResponse.model_validate(session)
