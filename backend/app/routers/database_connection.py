from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_session_key, get_workspace_key
from app.repositories import (
    DatabaseConnectionRepository,
    SessionRepository,
    WorkspaceRepository,
)
from app.schemas import DatabaseConnectionCreate, DatabaseConnectionResponse
from app.services import DatabaseConnectionService

router = APIRouter(prefix="/connection", tags=["connection"])


def get_database_connection_service(
    db: Session = Depends(get_db),
) -> DatabaseConnectionService:
    repository = DatabaseConnectionRepository(db)
    session_repository = SessionRepository(db)
    workspace_repository = WorkspaceRepository(db)
    return DatabaseConnectionService(repository, session_repository, workspace_repository)


@router.post("/", response_model=DatabaseConnectionResponse)
def create_database_connection(
    payload: DatabaseConnectionCreate,
    workspace_key: str = Depends(get_workspace_key),
    session_key: str = Depends(get_session_key),
    service: DatabaseConnectionService = Depends(get_database_connection_service),
) -> DatabaseConnectionResponse:
    connection = service.create_connection(workspace_key, session_key, payload)

    return DatabaseConnectionResponse(
        success=connection.is_connected,
        message=connection.status_message,
        database_type=connection.database_type,
        database_name=connection.database_name,
    )
