from pydantic import BaseModel


class WorkspaceCreate(BaseModel):
    name: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str


class WorkspaceResponse(BaseModel):
    workspace_key: str
    name: str | None = None

    model_config = {
        "from_attributes": True
    }
