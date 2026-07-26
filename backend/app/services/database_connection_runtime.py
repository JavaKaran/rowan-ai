from dataclasses import dataclass

from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import QueuePool

from app.core.database_connections import (
    build_connect_args,
    build_database_url,
    decrypt_password,
)
from app.models import DatabaseConnection
from app.schemas import DatabaseConnectionCreate


class DatabaseConnectionRuntime:
    def create_engine_for_payload(self, payload: DatabaseConnectionCreate) -> Engine:
        return create_engine(
            build_database_url(payload),
            poolclass=QueuePool,
            pool_size=1,
            max_overflow=0,
            pool_pre_ping=True,
            pool_timeout=5,
            connect_args=build_connect_args(payload.database_type),
        )

    def create_engine_for_connection(self, connection: DatabaseConnection) -> Engine:
        return create_engine(
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


@dataclass
class _ConnectionURLInput:
    database_type: str
    username: str
    password: str
    host: str
    port: int
    database_name: str
    ssl_mode: str | None
