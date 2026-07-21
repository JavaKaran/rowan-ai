from typing import Annotated

from fastapi import Header

from app.exceptions import SessionKeyMissing, WorkspaceKeyMissing


def get_workspace_key(
    x_workspace_key: Annotated[str | None, Header(alias="X-Workspace-Key")] = None,
) -> str:
    if not x_workspace_key or not x_workspace_key.strip():
        raise WorkspaceKeyMissing()

    return x_workspace_key


def get_session_key(
    x_session_key: Annotated[str | None, Header(alias="X-Session-Key")] = None,
) -> str:
    if not x_session_key or not x_session_key.strip():
        raise SessionKeyMissing()

    return x_session_key
