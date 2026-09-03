from sqlalchemy.orm import Session as DBSession

from app.models import QueryAttempt


class QueryAttemptRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create(self, query_attempt: QueryAttempt) -> QueryAttempt:
        self.db.add(query_attempt)
        self.db.flush()
        self.db.refresh(query_attempt)
        return query_attempt
