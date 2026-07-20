from app.exceptions import SessionNotFound
from app.models import Session
from app.repositories import SessionRepository
from app.services.identifier import IdentifierService


class SessionService:
    def __init__(self, repository: SessionRepository):
        self.repository = repository

    def create_session(self, name: str | None = None) -> Session:
        session_key = IdentifierService.session()
        session = Session(session_key=session_key, name=name)

        return self.repository.create(session)

    def get_session_by_key(self, session_key: str) -> Session:
        session = self.repository.get_by_key(session_key)
        if not session:
            raise SessionNotFound()

        return session

    def update_session(self, session_key: str, name: str) -> Session:
        session = self.repository.get_by_key(session_key)
        if not session:
            raise SessionNotFound()

        session.name = name
        return self.repository.update(session)
