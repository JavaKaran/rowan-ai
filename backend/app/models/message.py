from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .session import Session
from .workspace import Workspace


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False, default="query")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    workspace: Mapped[Workspace] = relationship()
    session: Mapped[Session] = relationship()
    query_record: Mapped["QueryRecord | None"] = relationship(
        back_populates="assistant_message",
        uselist=False,
    )
    prompt_record: Mapped["PromptRecord | None"] = relationship(
        back_populates="assistant_message",
        uselist=False,
    )
    tokens: Mapped[list["TokenUsage"]] = relationship(
        back_populates="message",
    )
