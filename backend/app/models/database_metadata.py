from typing import Any

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .database_connection import DatabaseConnection


class DatabaseMetadata(Base, TimestampMixin):
    __tablename__ = "database_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    database_connection_id: Mapped[int] = mapped_column(
        ForeignKey("database_connections.id"),
        index=True,
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    progress_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    database_connection: Mapped[DatabaseConnection] = relationship(
        back_populates="metadata_record",
    )
