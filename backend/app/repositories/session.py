from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from app.exceptions import SessionAlreadyExists
from app.models import Session


class SessionRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create(self, session: Session) -> Session:
        try:
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            return session
        except IntegrityError as exc:
            self.db.rollback()
            raise SessionAlreadyExists() from exc

    def get_by_key(self, session_key: str, workspace_id: int | None = None) -> Session | None:
        query = self.db.query(Session).filter(Session.session_key == session_key)
        if workspace_id is not None:
            query = query.filter(Session.workspace_id == workspace_id)

        return query.one_or_none()

    def update(self, session: Session) -> Session:
        self.db.commit()
        self.db.refresh(session)

        return session
