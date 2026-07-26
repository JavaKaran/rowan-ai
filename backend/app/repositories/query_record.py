from sqlalchemy.orm import Session as DBSession

from app.models import QueryRecord


class QueryRecordRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create(self, query_record: QueryRecord) -> QueryRecord:
        self.db.add(query_record)
        self.db.flush()
        self.db.refresh(query_record)
        return query_record
