from sqlalchemy.orm import Session as DBSession

from app.models import DatabaseConnection


class DatabaseConnectionRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create(self, connection: DatabaseConnection) -> DatabaseConnection:
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)

        return connection

    def has_successful_connection(self, session_id: int) -> bool:
        return (
            self.db.query(DatabaseConnection)
            .filter(
                DatabaseConnection.session_id == session_id,
                DatabaseConnection.is_connected.is_(True),
            )
            .first()
            is not None
        )
