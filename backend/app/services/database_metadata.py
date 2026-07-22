from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.pool import QueuePool

from app.core import get_logger
from app.core.database_connections import (
    build_connect_args,
    build_database_url,
    decrypt_password,
    format_database_error,
)
from app.db import SessionLocal
from app.models import DatabaseConnection, DatabaseMetadata
from app.repositories import DatabaseConnectionRepository, DatabaseMetadataRepository

logger = get_logger(__name__)

POSTGRES_SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "pg_toast"}
MYSQL_SYSTEM_SCHEMAS = {"information_schema", "performance_schema", "mysql", "sys"}


def parse_database_metadata_job(database_connection_id: int) -> None:
    with SessionLocal() as db:
        service = DatabaseMetadataService(
            db=db,
            connection_repository=DatabaseConnectionRepository(db),
            metadata_repository=DatabaseMetadataRepository(db),
        )
        service.parse_connection_metadata(database_connection_id)


class DatabaseMetadataService:
    def __init__(
        self,
        db: DBSession,
        connection_repository: DatabaseConnectionRepository,
        metadata_repository: DatabaseMetadataRepository,
    ):
        self.db = db
        self.connection_repository = connection_repository
        self.metadata_repository = metadata_repository

    def parse_connection_metadata(self, database_connection_id: int) -> None:
        metadata = self.metadata_repository.get_by_connection_id(database_connection_id)
        connection = self.connection_repository.get_by_id(database_connection_id)

        if not connection:
            logger.warning(
                "database_metadata.connection_not_found",
                database_connection_id=database_connection_id,
            )
            return

        if not metadata:
            metadata = self.metadata_repository.create_pending(database_connection_id)

        engine = None

        try:
            logger.info(
                "database_metadata.parse_started",
                database_connection_id=database_connection_id,
                database_type=connection.database_type,
                database_name=connection.database_name,
            )
            self.metadata_repository.update_status(metadata, "connecting")

            engine = create_engine(
                build_database_url(
                    _ConnectionURLInput(
                        database_type=connection.database_type,
                        username=connection.username,
                        password=decrypt_password(connection.encrypted_password),
                        host=connection.host,
                        port=connection.port,
                        database_name=connection.database_name,
                        ssl_mode=connection.ssl_mode,
                    )
                ),
                poolclass=QueuePool,
                pool_size=1,
                max_overflow=0,
                pool_pre_ping=True,
                pool_timeout=5,
                connect_args=build_connect_args(connection.database_type),
            )

            with engine.connect() as db_connection:
                db_connection.execute(text("select 1")).scalar_one()

            inspector = inspect(engine)
            self.metadata_repository.update_status(metadata, "discovering_tables")

            schemas = self._get_schema_names(connection, inspector)
            table_refs = self._get_table_refs(inspector, schemas)

            self.metadata_repository.update_status(
                metadata,
                "parsing_tables",
                progress_current=0,
                progress_total=len(table_refs),
            )

            metadata_json = self._build_metadata_json(
                connection=connection,
                inspector=inspector,
                schemas=schemas,
                table_refs=table_refs,
                metadata=metadata,
            )

            self.metadata_repository.update_status(
                metadata,
                "completed",
                progress_current=len(table_refs),
                progress_total=len(table_refs),
                metadata_json=metadata_json,
            )
            logger.info(
                "database_metadata.parse_completed",
                database_connection_id=database_connection_id,
                table_count=len(table_refs),
            )
        except Exception as exc:
            self.db.rollback()
            error_message = format_database_error(exc)
            logger.warning(
                "database_metadata.parse_failed",
                database_connection_id=database_connection_id,
                error=error_message,
            )
            self.metadata_repository.update_status(
                metadata,
                "failed",
                error_message=error_message,
            )
        finally:
            if engine:
                engine.dispose()

    def _build_metadata_json(
        self,
        connection: DatabaseConnection,
        inspector: Any,
        schemas: list[str | None],
        table_refs: list[tuple[str | None, str]],
        metadata: DatabaseMetadata,
    ) -> dict[str, Any]:
        tables_by_schema: dict[str | None, list[dict[str, Any]]] = {
            schema: [] for schema in schemas
        }
        relationships: list[dict[str, Any]] = []

        for index, (schema_name, table_name) in enumerate(table_refs, start=1):
            table_metadata = self._inspect_table(inspector, schema_name, table_name)
            tables_by_schema.setdefault(schema_name, []).append(table_metadata)

            for foreign_key in table_metadata["foreign_keys"]:
                relationships.append(
                    {
                        "from_schema": schema_name,
                        "from_table": table_name,
                        "from_columns": foreign_key["columns"],
                        "to_schema": foreign_key["referred_schema"],
                        "to_table": foreign_key["referred_table"],
                        "to_columns": foreign_key["referred_columns"],
                    }
                )

            self.metadata_repository.update_status(
                metadata,
                "parsing_tables",
                progress_current=index,
                progress_total=len(table_refs),
            )

        return {
            "database_type": connection.database_type,
            "database_name": connection.database_name,
            "schemas": [
                {
                    "name": schema_name,
                    "tables": tables_by_schema.get(schema_name, []),
                }
                for schema_name in schemas
            ],
            "relationships": relationships,
        }

    def _inspect_table(
        self,
        inspector: Any,
        schema_name: str | None,
        table_name: str,
    ) -> dict[str, Any]:
        columns = [
            {
                "name": column["name"],
                "type": str(column["type"]),
                "nullable": column.get("nullable"),
                "default": self._to_json_value(column.get("default")),
            }
            for column in inspector.get_columns(table_name, schema=schema_name)
        ]
        primary_key = inspector.get_pk_constraint(table_name, schema=schema_name)
        foreign_keys = [
            {
                "columns": foreign_key.get("constrained_columns", []),
                "referred_schema": foreign_key.get("referred_schema") or schema_name,
                "referred_table": foreign_key.get("referred_table"),
                "referred_columns": foreign_key.get("referred_columns", []),
            }
            for foreign_key in inspector.get_foreign_keys(table_name, schema=schema_name)
        ]

        return {
            "name": table_name,
            "columns": columns,
            "primary_key": primary_key.get("constrained_columns", []),
            "foreign_keys": foreign_keys,
        }

    def _get_schema_names(
        self,
        connection: DatabaseConnection,
        inspector: Any,
    ) -> list[str | None]:
        if connection.database_type == "mysql":
            return [connection.database_name]

        schemas = inspector.get_schema_names()
        if connection.database_type == "postgresql":
            return [
                schema
                for schema in schemas
                if schema not in POSTGRES_SYSTEM_SCHEMAS and not schema.startswith("pg_")
            ]

        return [
            schema
            for schema in schemas
            if schema not in POSTGRES_SYSTEM_SCHEMAS and schema not in MYSQL_SYSTEM_SCHEMAS
        ]

    def _get_table_refs(
        self,
        inspector: Any,
        schemas: list[str | None],
    ) -> list[tuple[str | None, str]]:
        table_refs: list[tuple[str | None, str]] = []

        for schema_name in schemas:
            for table_name in inspector.get_table_names(schema=schema_name):
                table_refs.append((schema_name, table_name))

        return table_refs

    def _to_json_value(self, value: Any) -> Any:
        if value is None or isinstance(value, str | int | float | bool):
            return value

        return str(value)


@dataclass
class _ConnectionURLInput:
    database_type: str
    username: str
    password: str
    host: str
    port: int
    database_name: str
    ssl_mode: str | None
