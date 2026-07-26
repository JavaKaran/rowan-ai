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
