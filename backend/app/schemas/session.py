from pydantic import BaseModel, Field

from .query import QueryResponse


class SessionCreate(BaseModel):
    name: str | None = None


class SessionUpdate(BaseModel):
    name: str


class SessionQueryHistoryItem(QueryResponse):
    question: str
    status: str
    error_message: str | None = None


class SessionResponse(BaseModel):
    session_key: str
    name: str | None = None
    messages: list[SessionQueryHistoryItem] = Field(default_factory=list)

    model_config = {
        "from_attributes": True
    }


class SessionListItem(BaseModel):
    session_key: str
    name: str | None = None
    first_message: str | None = None

    model_config = {
        "from_attributes": True
    }


class SessionListResponse(BaseModel):
    items: list[SessionListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
