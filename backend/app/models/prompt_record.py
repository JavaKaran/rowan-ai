from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .message import Message


class PromptRecord(Base, TimestampMixin):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    assistant_message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id"),
        index=True,
        nullable=False,
        unique=True,
    )
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_text: Mapped[str] = mapped_column(Text, nullable=False)
    user_question: Mapped[str] = mapped_column(Text, nullable=False)

    assistant_message: Mapped[Message] = relationship(back_populates="prompt_record")
