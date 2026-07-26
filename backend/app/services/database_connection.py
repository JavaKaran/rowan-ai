from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool

from app.core.database_connections import (
    build_connect_args,
    build_database_url,
    decrypt_password,
    encrypt_password,
    format_database_error,
)
from app.core import get_logger, mask_value
from app.exceptions import (
    DatabaseConnectionAlreadyExists,
    SessionNotFound,
    WorkspaceNotFound,
)
from app.models import DatabaseConnection
from app.repositories import (
    DatabaseConnectionRepository,
    DatabaseMetadataRepository,
    SessionRepository,
    WorkspaceRepository,
)
from app.schemas import DatabaseConnectionCreate
from app.services.database_connection_runtime import DatabaseConnectionRuntime
from app.services.metadata_jobs import MetadataJobDispatcher

logger = get_logger(__name__)


class DatabaseConnectionService:
    def __init__(
        self,
        repository: DatabaseConnectionRepository,
        metadata_repository: DatabaseMetadataRepository,
        metadata_job_dispatcher: MetadataJobDispatcher,
        session_repository: SessionRepository,
        workspace_repository: WorkspaceRepository,
        connection_runtime: DatabaseConnectionRuntime,
    ):
        self.repository = repository
        self.metadata_repository = metadata_repository
        self.metadata_job_dispatcher = metadata_job_dispatcher
        self.session_repository = session_repository
        self.workspace_repository = workspace_repository
        self.connection_runtime = connection_runtime

    def create_connection(
        self,
        workspace_key: str,
        session_key: str,
        payload: DatabaseConnectionCreate,
    ) -> DatabaseConnection:
        logger.info(
            "database_connection.create_started",
            workspace_key=mask_value(workspace_key),
            session_key=mask_value(session_key),
            database_type=payload.database_type,
            host=payload.host,
            port=payload.port,
            database_name=payload.database_name,
            username=mask_value(payload.username),
            ssl_mode=payload.ssl_mode,
        )

        workspace = self.workspace_repository.get_by_key(workspace_key)
        if not workspace:
            logger.warning(
                "database_connection.workspace_not_found",
                workspace_key=mask_value(workspace_key),
            )
            raise WorkspaceNotFound()

        session = self.session_repository.get_by_key(session_key, workspace.id)
        if not session:
            logger.warning(
                "database_connection.session_not_found",
                workspace_id=workspace.id,
                session_key=mask_value(session_key),
            )
            raise SessionNotFound()

        existing_connection = self.repository.get_successful_connection(session.id)
        if existing_connection:
            if not self._is_same_connection(existing_connection, payload):
                logger.warning(
                    "database_connection.different_connection_already_exists",
                    session_id=session.id,
                    existing_connection_id=existing_connection.id,
                    database_type=payload.database_type,
                    host=payload.host,
                    port=payload.port,
                    database_name=payload.database_name,
                    username=mask_value(payload.username),
                )
                raise DatabaseConnectionAlreadyExists()

            self._enqueue_metadata_parsing(existing_connection)
            logger.info(
                "database_connection.existing_reused",
                connection_id=existing_connection.id,
                session_id=session.id,
            )
            return existing_connection

        success, message = self._validate_connection(payload)
        connection = DatabaseConnection(
            session_id=session.id,
            database_type=payload.database_type,
            host=payload.host,
            port=payload.port,
            database_name=payload.database_name,
            username=payload.username,
            encrypted_password=encrypt_password(payload.password.get_secret_value()),
            ssl_mode=payload.ssl_mode,
            is_connected=success,
            status_message=message,
        )

        connection = self.repository.create(connection)

        if connection.is_connected:
            self.metadata_repository.create_pending(connection.id)
            self.metadata_job_dispatcher.enqueue_parse_metadata(connection.id)
            logger.info(
                "database_connection.metadata_parse_enqueued",
                connection_id=connection.id,
            )

        logger.info(
            "database_connection.saved",
            connection_id=connection.id,
            session_id=session.id,
            success=connection.is_connected,
            database_type=connection.database_type,
            host=connection.host,
            port=connection.port,
            database_name=connection.database_name,
        )

        return connection

    def _is_same_connection(
        self,
        connection: DatabaseConnection,
        payload: DatabaseConnectionCreate,
    ) -> bool:
        return (
            connection.database_type == payload.database_type
            and connection.host == payload.host
            and connection.port == payload.port
            and connection.database_name == payload.database_name
            and connection.username == payload.username
            and connection.ssl_mode == payload.ssl_mode
            and decrypt_password(connection.encrypted_password)
            == payload.password.get_secret_value()
        )

    def _enqueue_metadata_parsing(self, connection: DatabaseConnection) -> None:
        metadata = self.metadata_repository.get_by_connection_id(connection.id)

        if metadata:
            self.metadata_repository.update_status(
                metadata,
                "pending",
                progress_current=0,
                progress_total=0,
                error_message=None,
            )
        else:
            self.metadata_repository.create_pending(connection.id)

        self.metadata_job_dispatcher.enqueue_parse_metadata(connection.id)
        logger.info(
            "database_connection.metadata_parse_enqueued",
            connection_id=connection.id,
        )

    def _validate_connection(self, payload: DatabaseConnectionCreate) -> tuple[bool, str]:
        engine = None
        logger.info(
            "database_connection.validation_started",
            database_type=payload.database_type,
            host=payload.host,
            port=payload.port,
            database_name=payload.database_name,
            username=mask_value(payload.username),
            ssl_mode=payload.ssl_mode,
        )

        try:
            engine = self.connection_runtime.create_engine_for_payload(payload)
            with engine.connect() as connection:
                result = connection.execute(text("select 1"))
                result.scalar_one()

            logger.info(
                "database_connection.validation_succeeded",
                database_type=payload.database_type,
                host=payload.host,
                port=payload.port,
                database_name=payload.database_name,
            )
            return True, "Database connection established successfully."
        except (ImportError, SQLAlchemyError) as exc:
            error_message = format_database_error(exc)
            logger.warning(
                "database_connection.validation_failed",
                database_type=payload.database_type,
                host=payload.host,
                port=payload.port,
                database_name=payload.database_name,
                error=error_message,
            )
            return False, f"Database connection failed: {error_message}"
        finally:
            if engine:
                engine.dispose()
                logger.info(
                    "database_connection.validation_engine_disposed",
                    database_type=payload.database_type,
                    host=payload.host,
                    port=payload.port,
                    database_name=payload.database_name,
                )
