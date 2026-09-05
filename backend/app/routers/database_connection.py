from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_session_key, get_workspace_key
from app.repositories import (
    DatabaseConnectionRepository,
    DatabaseMetadataRepository,
    SessionRepository,
    WorkspaceRepository,
)
from app.schemas import (
    DatabaseConnectionCreate,
    DatabaseConnectionResponse,
    DatabaseMetadataStatusResponse,
)
from app.services import DatabaseConnectionService
from app.services.database_connection_runtime import DatabaseConnectionRuntime
from app.services.metadata_jobs import MetadataJobDispatcher, get_metadata_job_dispatcher

router = APIRouter(prefix="/connection", tags=["connection"])


def get_database_connection_service(
    db: Session = Depends(get_db),
    metadata_job_dispatcher: MetadataJobDispatcher = Depends(get_metadata_job_dispatcher),
) -> DatabaseConnectionService:
    repository = DatabaseConnectionRepository(db)
    metadata_repository = DatabaseMetadataRepository(db)
    session_repository = SessionRepository(db)
    workspace_repository = WorkspaceRepository(db)
    return DatabaseConnectionService(
        repository,
        metadata_repository,
        metadata_job_dispatcher,
        session_repository,
        workspace_repository,
        DatabaseConnectionRuntime(),
    )


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


@router.get("/metadata-status", response_model=DatabaseMetadataStatusResponse)
def get_database_metadata_status(
    workspace_key: str = Depends(get_workspace_key),
    session_key: str = Depends(get_session_key),
    service: DatabaseConnectionService = Depends(get_database_connection_service),
) -> DatabaseMetadataStatusResponse:
    return DatabaseMetadataStatusResponse(
        **service.get_metadata_status(workspace_key, session_key)
    )
