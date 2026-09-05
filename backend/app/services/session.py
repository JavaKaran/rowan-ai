import math
from typing import Any

from app.exceptions import SessionNotFound, WorkspaceNotFound
from app.models import Session
from app.repositories import (
    MessageRepository,
    QueryRecordRepository,
    SessionRepository,
    WorkspaceRepository,
)
from app.schemas import (
    QueryToolCallInfo,
    QueryTokenUsage,
    SessionListItem,
    SessionListResponse,
    SessionQueryHistoryItem,
)
from app.services.identifier import IdentifierService

SESSION_LIST_PAGE_SIZE = 20


class SessionService:
    def __init__(
        self,
        repository: SessionRepository,
        workspace_repository: WorkspaceRepository,
        query_record_repository: QueryRecordRepository | None = None,
        message_repository: MessageRepository | None = None,
    ):
        self.repository = repository
        self.workspace_repository = workspace_repository
        self.query_record_repository = query_record_repository
        self.message_repository = message_repository

    def create_session(self, workspace_key: str, name: str | None = None) -> Session:
        workspace = self.workspace_repository.get_by_key(workspace_key)
        if not workspace:
            raise WorkspaceNotFound()

        session_key = IdentifierService.session()
        session = Session(
            session_key=session_key,
            workspace_id=workspace.id,
            name=name,
        )

        return self.repository.create(session)

    def get_session_by_key(self, workspace_key: str | None, session_key: str) -> Session:
        if workspace_key:
            workspace = self.workspace_repository.get_by_key(workspace_key)
            if not workspace:
                raise WorkspaceNotFound()

            session = self.repository.get_by_key(session_key, workspace.id)
        else:
            session = self.repository.get_by_key(session_key)

        if not session:
            raise SessionNotFound()

        return session

    def update_session(self, workspace_key: str, session_key: str, name: str) -> Session:
        workspace = self.workspace_repository.get_by_key(workspace_key)
        if not workspace:
            raise WorkspaceNotFound()

        session = self.repository.get_by_key(session_key, workspace.id)
        if not session:
            raise SessionNotFound()

        session.name = name
        return self.repository.update(session)

    def list_sessions(self, workspace_key: str, page: int = 1) -> SessionListResponse:
        workspace = self.workspace_repository.get_by_key(workspace_key)
        if not workspace:
            raise WorkspaceNotFound()

        sessions, total = self.repository.list_for_workspace(
            workspace.id, page, SESSION_LIST_PAGE_SIZE
        )
        return SessionListResponse(
            items=[
                SessionListItem(
                    session_key=session.session_key,
                    name=session.name,
                    first_message=self._first_message(session),
                )
                for session in sessions
            ],
            page=page,
            page_size=SESSION_LIST_PAGE_SIZE,
            total=total,
            total_pages=math.ceil(total / SESSION_LIST_PAGE_SIZE) if total else 0,
        )

    def _first_message(self, session: Any) -> str | None:
        if not self.message_repository:
            return None
        first_message = self.message_repository.get_first_user_query(session.id)
        return first_message.content if first_message else None

    def get_session_history(self, session_id: int) -> list[SessionQueryHistoryItem]:
        query_records = self.query_record_repository.list_for_session(session_id)
        return [self._to_history_item(query_record) for query_record in query_records]

    def _to_history_item(self, query_record: Any) -> SessionQueryHistoryItem:
        tokens = query_record.assistant_message.tokens
        token_usage = tokens[0] if tokens else None
        tool_calls = [
            QueryToolCallInfo(
                attempt_number=attempt.attempt_number,
                name=call.get("name"),
                args=call.get("args"),
                result=call.get("result"),
            )
            for attempt in query_record.attempts
            for call in attempt.tool_calls
        ]
        return SessionQueryHistoryItem(
            question=query_record.assistant_message.prompt_record.user_question,
            status=query_record.status,
            error_message=query_record.error_message,
            sql_query=query_record.sql_query,
            summary=query_record.assistant_message.content,
            columns=query_record.response_columns,
            rows=query_record.response_rows,
            row_count=query_record.row_count,
            execution_time_ms=query_record.execution_time_ms,
            truncated=query_record.truncated,
            token_usage=QueryTokenUsage(
                total_tokens=token_usage.total_tokens if token_usage else 0,
                input_tokens=token_usage.input_tokens if token_usage else 0,
                output_tokens=token_usage.output_tokens if token_usage else 0,
                cached_input_tokens=token_usage.cached_input_tokens if token_usage else 0,
            ),
            attempt_count=len(query_record.attempts),
            repaired=query_record.status == "completed" and len(query_record.attempts) > 1,
            tool_calls=tool_calls,
        )
