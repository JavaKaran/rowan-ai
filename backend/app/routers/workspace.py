from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import WorkspaceService
from app.repositories import WorkspaceRepository
from app.schemas import WorkspaceCreate, WorkspaceResponse, WorkspaceUpdate

router = APIRouter(prefix="/workspace", tags=["workspace"])

def get_workspace_service(db: Session = Depends(get_db)) -> WorkspaceService:
    repository = WorkspaceRepository(db)
    return WorkspaceService(repository)

@router.post("/", response_model=WorkspaceResponse)
def create_workspace(
    payload: WorkspaceCreate,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceResponse:
    workspace = service.create_workspace(payload.name)
    return WorkspaceResponse.model_validate(workspace)

@router.get("/{workspace_key}", response_model=WorkspaceResponse)
def get_workspace(
    workspace_key: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceResponse:
    workspace = service.get_workspace_by_key(workspace_key)
    return WorkspaceResponse.model_validate(workspace)

@router.patch("/{workspace_key}", response_model=WorkspaceResponse)
def update_workspace(
    workspace_key: str,
    payload: WorkspaceUpdate,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceResponse:
    workspace = service.update_workspace(workspace_key, payload.name)
    return WorkspaceResponse.model_validate(workspace)
