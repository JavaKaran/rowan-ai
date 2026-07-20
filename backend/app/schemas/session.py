from pydantic import BaseModel


class SessionCreate(BaseModel):
    name: str | None = None


class SessionUpdate(BaseModel):
    name: str


class SessionResponse(BaseModel):
    session_key: str
    name: str | None = None

    model_config = {
        "from_attributes": True
    }
