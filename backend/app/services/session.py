from app.exceptions import SessionNotFound, WorkspaceNotFound
from app.models import Session
from app.repositories import SessionRepository, WorkspaceRepository
from app.services.identifier import IdentifierService


class SessionService:
    def __init__(
        self,
        repository: SessionRepository,
        workspace_repository: WorkspaceRepository,
    ):
        self.repository = repository
        self.workspace_repository = workspace_repository

    def create_session(self, workspace_key: str, name: str | None = None) -> Session:
        workspace = self.workspace_repository.get_by_key(workspace_key)
        if not workspace:
            raise WorkspaceNotFound()

        session_key = IdentifierService.session()
        session = Session(
            session_key=session_key,
            workspace_id=workspace.id,
            name=name,
        )

        return self.repository.create(session)

    def get_session_by_key(self, workspace_key: str | None, session_key: str) -> Session:
        if workspace_key:
            workspace = self.workspace_repository.get_by_key(workspace_key)
            if not workspace:
                raise WorkspaceNotFound()

            session = self.repository.get_by_key(session_key, workspace.id)
        else:
            session = self.repository.get_by_key(session_key)

        if not session:
            raise SessionNotFound()

        return session

    def update_session(self, workspace_key: str, session_key: str, name: str) -> Session:
        workspace = self.workspace_repository.get_by_key(workspace_key)
        if not workspace:
            raise WorkspaceNotFound()

        session = self.repository.get_by_key(session_key, workspace.id)
        if not session:
            raise SessionNotFound()

        session.name = name
        return self.repository.update(session)
