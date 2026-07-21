import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool

from app.exceptions import (
    DatabaseConnectionAlreadyExists,
    EncryptionKeyMissing,
    SessionNotFound,
    WorkspaceNotFound,
)
from app.models import DatabaseConnection
from app.repositories import (
    DatabaseConnectionRepository,
    SessionRepository,
    WorkspaceRepository,
)
from app.schemas import DatabaseConnectionCreate


class DatabaseConnectionService:
    def __init__(
        self,
        repository: DatabaseConnectionRepository,
        session_repository: SessionRepository,
        workspace_repository: WorkspaceRepository,
    ):
        self.repository = repository
        self.session_repository = session_repository
        self.workspace_repository = workspace_repository

    def create_connection(
        self,
        workspace_key: str,
        session_key: str,
        payload: DatabaseConnectionCreate,
    ) -> DatabaseConnection:
        workspace = self.workspace_repository.get_by_key(workspace_key)
        if not workspace:
            raise WorkspaceNotFound()

        session = self.session_repository.get_by_key(session_key, workspace.id)
        if not session:
            raise SessionNotFound()

        if self.repository.has_successful_connection(session.id):
            raise DatabaseConnectionAlreadyExists()

        success, message = self._validate_connection(payload)
        connection = DatabaseConnection(
            session_id=session.id,
            database_type=payload.database_type,
            host=payload.host,
            port=payload.port,
            database_name=payload.database_name,
            username=payload.username,
            encrypted_password=self._encrypt_password(payload.password.get_secret_value()),
            ssl_mode=payload.ssl_mode,
            is_connected=success,
            status_message=message,
        )

        return self.repository.create(connection)

    def _validate_connection(self, payload: DatabaseConnectionCreate) -> tuple[bool, str]:
        engine = None
        try:
            engine = create_engine(
                self._build_database_url(payload),
                poolclass=QueuePool,
                pool_size=1,
                max_overflow=0,
                pool_pre_ping=True,
                pool_timeout=5,
                connect_args=self._build_connect_args(payload),
            )
            with engine.connect() as connection:
                result = connection.execute(text("select 1"))
                result.scalar_one()

            return True, "Database connection established successfully."
        except (ImportError, SQLAlchemyError) as exc:
            return False, f"Database connection failed: {self._format_connection_error(exc)}"
        finally:
            if engine:
                engine.dispose()

    def _build_database_url(self, payload: DatabaseConnectionCreate) -> URL:
        drivername = {
            "postgresql": "postgresql+psycopg2",
            "mysql": "mysql+pymysql",
        }[payload.database_type]

        query = {}
        if payload.database_type == "postgresql" and payload.ssl_mode:
            query["sslmode"] = payload.ssl_mode

        return URL.create(
            drivername=drivername,
            username=payload.username,
            password=payload.password.get_secret_value(),
            host=payload.host,
            port=payload.port,
            database=payload.database_name,
            query=query,
        )

    def _build_connect_args(self, payload: DatabaseConnectionCreate) -> dict:
        if payload.database_type == "postgresql":
            return {"connect_timeout": 5}

        if payload.database_type == "mysql":
            return {"connect_timeout": 5}

        return {}

    def _encrypt_password(self, password: str) -> str:
        key = os.getenv("DATABASE_CONNECTION_ENCRYPTION_KEY")
        if not key:
            raise EncryptionKeyMissing()

        try:
            return Fernet(key.encode()).encrypt(password.encode()).decode()
        except (ValueError, InvalidToken) as exc:
            raise EncryptionKeyMissing() from exc

    def _format_connection_error(self, exc: Exception) -> str:
        message = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
        return message.splitlines()[0]
