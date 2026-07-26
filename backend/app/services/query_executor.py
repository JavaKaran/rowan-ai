import time
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.database_connections import format_database_error
from app.exceptions import SQLExecutionFailed
from app.models import DatabaseConnection
from app.schemas import QueryResponse, QueryTokenUsage
from app.services.database_connection_runtime import DatabaseConnectionRuntime


class SQLQueryExecutor:
    def __init__(
        self,
        connection_runtime: DatabaseConnectionRuntime,
        max_rows: int = 200,
        statement_timeout_ms: int = 5000,
    ):
        self.connection_runtime = connection_runtime
        self.max_rows = max_rows
        self.statement_timeout_ms = statement_timeout_ms

    def execute(self, connection: DatabaseConnection, sql_text: str) -> QueryResponse:
        engine = None
        started_at = time.perf_counter()
        try:
            engine = self.connection_runtime.create_engine_for_connection(connection)
            with engine.connect() as db_connection:
                self._apply_timeout(db_connection, connection.database_type)
                result = db_connection.execute(text(sql_text))
                columns = list(result.keys())
                raw_rows = result.fetchmany(self.max_rows + 1)

            truncated = len(raw_rows) > self.max_rows
            selected_rows = raw_rows[: self.max_rows]
            rows = [jsonable_encoder(dict(row._mapping)) for row in selected_rows]
            execution_time_ms = int((time.perf_counter() - started_at) * 1000)
            return QueryResponse(
                sql_query=sql_text,
                summary="",
                columns=columns,
                rows=rows,
                row_count=len(selected_rows),
                execution_time_ms=execution_time_ms,
                truncated=truncated,
                token_usage=QueryTokenUsage(
                    total_tokens=0,
                    input_tokens=0,
                    output_tokens=0,
                    cached_input_tokens=0,
                ),
            )
        except SQLAlchemyError as exc:
            raise SQLExecutionFailed(
                f"Query execution failed: {format_database_error(exc)}"
            ) from exc
        finally:
            if engine:
                engine.dispose()

    def _apply_timeout(self, db_connection: Any, database_type: str) -> None:
        if database_type == "postgresql":
            db_connection.execute(
                text("SET statement_timeout = :timeout_ms"),
                {"timeout_ms": self.statement_timeout_ms},
            )
            return

        if database_type == "mysql":
            db_connection.execute(
                text("SET SESSION MAX_EXECUTION_TIME = :timeout_ms"),
                {"timeout_ms": self.statement_timeout_ms},
            )
