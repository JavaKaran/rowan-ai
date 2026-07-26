from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .database_connection import DatabaseConnection
from .message import Message


class QueryRecord(Base, TimestampMixin):
    __tablename__ = "queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    assistant_message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id"),
        index=True,
        nullable=False,
        unique=True,
    )
    database_connection_id: Mapped[int] = mapped_column(
        ForeignKey("database_connections.id"),
        index=True,
        nullable=False,
    )
    sql_query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_columns: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    response_rows: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    assistant_message: Mapped[Message] = relationship(back_populates="query_record")
    database_connection: Mapped[DatabaseConnection] = relationship()
