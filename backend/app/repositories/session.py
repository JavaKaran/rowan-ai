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

    def list_for_workspace(
        self, workspace_id: int, page: int, page_size: int
    ) -> tuple[list[Session], int]:
        query = self.db.query(Session).filter(Session.workspace_id == workspace_id)
        total = query.count()
        items = (
            query.order_by(Session.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total
