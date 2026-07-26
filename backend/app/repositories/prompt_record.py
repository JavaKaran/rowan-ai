from sqlalchemy.orm import Session as DBSession

from app.models import PromptRecord


class PromptRecordRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create(self, prompt_record: PromptRecord) -> PromptRecord:
        self.db.add(prompt_record)
        self.db.flush()
        self.db.refresh(prompt_record)
        return prompt_record
