from sqlalchemy.orm import Session as DBSession

from app.models import Message


class MessageRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create(self, message: Message) -> Message:
        self.db.add(message)
        self.db.flush()
        self.db.refresh(message)
        return message

    def get_last_user_query(self, session_id: int) -> Message | None:
        return (
            self.db.query(Message)
            .filter(
                Message.session_id == session_id,
                Message.role == "user",
                Message.message_type == "query",
            )
            .order_by(Message.id.desc())
            .first()
        )

    def get_first_user_query(self, session_id: int) -> Message | None:
        return (
            self.db.query(Message)
            .filter(
                Message.session_id == session_id,
                Message.role == "user",
                Message.message_type == "query",
            )
            .order_by(Message.id.asc())
            .first()
        )
