from .base import Base, TimestampMixin
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workspace_key: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    
    
