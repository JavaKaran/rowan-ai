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

    def get_by_id(self, connection_id: int) -> DatabaseConnection | None:
        return (
            self.db.query(DatabaseConnection)
            .filter(DatabaseConnection.id == connection_id)
            .first()
        )

    def get_successful_connection(self, session_id: int) -> DatabaseConnection | None:
        return (
            self.db.query(DatabaseConnection)
            .filter(
                DatabaseConnection.session_id == session_id,
                DatabaseConnection.is_connected.is_(True),
            )
            .first()
        )

    def has_successful_connection(self, session_id: int) -> bool:
        return self.get_successful_connection(session_id) is not None
