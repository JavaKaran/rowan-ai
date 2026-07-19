from app.services.identifier import IdentifierService
from app.repositories import WorkspaceRepository
from app.models import Workspace
from app.exceptions import WorkspaceNotFound


class WorkspaceService:
    def __init__(self, repository: WorkspaceRepository):
        self.repository = repository
    
    def create_workspace(self, name: str | None = None) -> Workspace:
        workspace_key = IdentifierService.workspace()
        workspace = Workspace(workspace_key=workspace_key, name=name)
        
        return self.repository.create(workspace)
    
    def get_workspace_by_key(self, workspace_key: str) -> Workspace:
        workspace = self.repository.get_by_key(workspace_key)
        if not workspace:
            raise WorkspaceNotFound()
        
        return workspace
    
    def update_workspace(self, workspace_key: str, name: str) -> Workspace:
        workspace = self.repository.get_by_key(workspace_key)
        if not workspace:
            raise WorkspaceNotFound()
        
        workspace.name = name
        return self.repository.update(workspace)
            
