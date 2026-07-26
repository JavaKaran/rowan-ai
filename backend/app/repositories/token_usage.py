from sqlalchemy.orm import Session as DBSession

from app.models import TokenUsage


class TokenUsageRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create(self, token_usage: TokenUsage) -> TokenUsage:
        self.db.add(token_usage)
        self.db.flush()
        self.db.refresh(token_usage)
        return token_usage
