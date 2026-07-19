from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.exceptions import WorkspaceAlreadyExists
from app.models import Workspace


class WorkspaceRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, workspace: Workspace) -> Workspace:
        try:
            self.db.add(workspace)
            self.db.commit()
            self.db.refresh(workspace)
            
            return workspace
        except IntegrityError as exc:
            self.db.rollback()
            raise WorkspaceAlreadyExists() from exc
    
    def get_by_key(self, workspace_key: str) -> Workspace | None:
        return (
            self.db.query(Workspace)
            .filter(Workspace.workspace_key == workspace_key)
            .one_or_none()
        )
    
    def update(self, workspace: Workspace) -> Workspace:
        self.db.commit()
        self.db.refresh(workspace)
        
        return workspace
