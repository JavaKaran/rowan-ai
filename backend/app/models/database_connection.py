from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .session import Session


class DatabaseConnection(Base, TimestampMixin):
    __tablename__ = "database_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True, nullable=False)
    database_type: Mapped[str] = mapped_column(String(32), nullable=False)
    host: Mapped[str] = mapped_column(String, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database_name: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    encrypted_password: Mapped[str] = mapped_column(Text, nullable=False)
    ssl_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status_message: Mapped[str] = mapped_column(Text, nullable=False)

    session: Mapped[Session] = relationship()
    metadata_record: Mapped["DatabaseMetadata | None"] = relationship(
        back_populates="database_connection",
        uselist=False,
    )
