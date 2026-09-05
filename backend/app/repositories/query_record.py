from sqlalchemy.orm import Session as DBSession, joinedload

from app.models import Message, QueryRecord


class QueryRecordRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create(self, query_record: QueryRecord) -> QueryRecord:
        self.db.add(query_record)
        self.db.flush()
        self.db.refresh(query_record)
        return query_record

    def get_last_completed_for_session(self, session_id: int) -> QueryRecord | None:
        return (
            self.db.query(QueryRecord)
            .join(Message, QueryRecord.assistant_message_id == Message.id)
            .filter(
                Message.session_id == session_id,
                QueryRecord.status == "completed",
            )
            .order_by(QueryRecord.id.desc())
            .first()
        )

    def list_for_session(self, session_id: int) -> list[QueryRecord]:
        return (
            self.db.query(QueryRecord)
            .join(Message, QueryRecord.assistant_message_id == Message.id)
            .filter(Message.session_id == session_id)
            .options(
                joinedload(QueryRecord.assistant_message).joinedload(Message.prompt_record),
                joinedload(QueryRecord.assistant_message).joinedload(Message.tokens),
                joinedload(QueryRecord.attempts),
            )
            .order_by(QueryRecord.id.asc())
            .all()
        )
