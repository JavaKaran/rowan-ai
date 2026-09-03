from typing import Any

from app.core import get_logger, mask_value
from app.exceptions import (
    DatabaseConnectionNotFound,
    DatabaseMetadataNotReady,
    SQLExecutionFailed,
    SQLGenerationFailed,
    SessionNotFound,
    WorkspaceNotFound,
)
from app.models import DatabaseConnection, Message, PromptRecord, QueryRecord, TokenUsage
from app.repositories import (
    DatabaseConnectionRepository,
    DatabaseMetadataRepository,
    MessageRepository,
    PromptRecordRepository,
    QueryRecordRepository,
    SessionRepository,
    TokenUsageRepository,
    WorkspaceRepository,
)
from app.schemas import QueryResponse
from app.services.query_agent import AGENT_SYSTEM_PROMPT
from app.services.query_executor import SQLQueryExecutor
from app.services.query_guardrails import BeforeGuardrail
from app.services.query_prompt_builder import QueryPromptBuilder
from app.services.query_repair import QueryRepairLoop

logger = get_logger(__name__)


class QueryService:
    def __init__(
        self,
        db: Any,
        connection_repository: DatabaseConnectionRepository,
        metadata_repository: DatabaseMetadataRepository,
        session_repository: SessionRepository,
        workspace_repository: WorkspaceRepository,
        message_repository: MessageRepository,
        prompt_record_repository: PromptRecordRepository,
        query_record_repository: QueryRecordRepository,
        token_usage_repository: TokenUsageRepository,
        prompt_builder: QueryPromptBuilder,
        before_guardrail: BeforeGuardrail,
        repair_loop: QueryRepairLoop,
        query_executor: SQLQueryExecutor,
    ):
        self.db = db
        self.connection_repository = connection_repository
        self.metadata_repository = metadata_repository
        self.session_repository = session_repository
        self.workspace_repository = workspace_repository
        self.message_repository = message_repository
        self.prompt_record_repository = prompt_record_repository
        self.query_record_repository = query_record_repository
        self.token_usage_repository = token_usage_repository
        self.prompt_builder = prompt_builder
        self.before_guardrail = before_guardrail
        self.repair_loop = repair_loop
        self.query_executor = query_executor

    def run_query(
        self,
        workspace_key: str,
        session_key: str,
        question: str,
    ) -> QueryResponse:
        workspace, session, connection, metadata_json = self._resolve_connection_and_metadata(
            workspace_key,
            session_key,
        )
        validated_question = self.before_guardrail.check(question)
        previous_context = self._load_previous_context(session.id)
        prompt_input = self.prompt_builder.build(
            metadata_json=metadata_json,
            question=validated_question,
            last_user_question=previous_context["last_user_question"],
            last_sql_query=previous_context["last_sql_query"],
        )
        prompt_input["system_prompt"] = AGENT_SYSTEM_PROMPT

        logger.info(
            "query.generation_started",
            workspace_key=mask_value(workspace_key),
            session_key=mask_value(session_key),
            database_type=connection.database_type,
            database_name=connection.database_name,
        )
        outcome = self.repair_loop.run(
            question=validated_question,
            metadata_json=metadata_json,
            last_user_question=previous_context["last_user_question"],
            last_sql_query=previous_context["last_sql_query"],
        )

        if not outcome.success:
            last_attempt = outcome.attempts[-1] if outcome.attempts else None
            logger.warning(
                "query.generation_failed_after_repair",
                workspace_key=mask_value(workspace_key),
                session_key=mask_value(session_key),
                attempts=outcome.attempt_count,
                failure_category=last_attempt.failure_category if last_attempt else None,
                failure_detail=last_attempt.failure_detail if last_attempt else None,
            )
            raise SQLGenerationFailed(
                last_attempt.failure_detail if last_attempt else "SQL generation failed."
            )

        generation_result = outcome.generation_result
        logger.info(
            "query.generation_succeeded",
            workspace_key=mask_value(workspace_key),
            session_key=mask_value(session_key),
            attempts=outcome.attempt_count,
            repaired=outcome.repaired,
        )

        try:
            result = self.query_executor.execute(connection, outcome.sql_query)
        except SQLExecutionFailed as exc:
            self._persist_query_turn(
                workspace_id=workspace.id,
                session_id=session.id,
                connection=connection,
                question=validated_question,
                prompt_input=prompt_input,
                sql_query=outcome.sql_query,
                summary=generation_result.summary,
                token_usage=outcome.total_token_usage,
                provider=generation_result.provider,
                model_name=generation_result.model_name,
                query_status="failed",
                query_error_message=str(exc),
            )
            raise
        result.summary = generation_result.summary
        result.token_usage = outcome.total_token_usage
        self._persist_query_turn(
            workspace_id=workspace.id,
            session_id=session.id,
            connection=connection,
            question=validated_question,
            prompt_input=prompt_input,
            sql_query=result.sql_query,
            summary=result.summary,
            token_usage=result.token_usage,
            provider=generation_result.provider,
            model_name=generation_result.model_name,
            query_status="completed",
            query_error_message=None,
            result=result,
        )

        logger.info(
            "query.execution_succeeded",
            workspace_key=mask_value(workspace_key),
            session_key=mask_value(session_key),
            database_name=connection.database_name,
            row_count=result.row_count,
            truncated=result.truncated,
            execution_time_ms=result.execution_time_ms,
            total_tokens=result.token_usage.total_tokens,
            input_tokens=result.token_usage.input_tokens,
            output_tokens=result.token_usage.output_tokens,
            cached_input_tokens=result.token_usage.cached_input_tokens,
        )
        return result

    def _resolve_connection_and_metadata(
        self,
        workspace_key: str,
        session_key: str,
    ) -> tuple[Any, Any, DatabaseConnection, dict[str, Any]]:
        workspace = self.workspace_repository.get_by_key(workspace_key)
        if not workspace:
            raise WorkspaceNotFound()

        session = self.session_repository.get_by_key(session_key, workspace.id)
        if not session:
            raise SessionNotFound()

        connection = self.connection_repository.get_successful_connection(session.id)
        if not connection:
            raise DatabaseConnectionNotFound()

        metadata = self.metadata_repository.get_by_connection_id(connection.id)
        if not metadata or metadata.status != "completed" or not metadata.metadata_json:
            raise DatabaseMetadataNotReady()

        return workspace, session, connection, metadata.metadata_json

    def _persist_query_turn(
        self,
        workspace_id: int,
        session_id: int,
        connection: DatabaseConnection,
        question: str,
        prompt_input: dict[str, str],
        sql_query: str,
        summary: str,
        token_usage: Any,
        provider: str,
        model_name: str,
        query_status: str,
        query_error_message: str | None,
        result: QueryResponse | None = None,
    ) -> None:
        self.message_repository.create(
            Message(
                workspace_id=workspace_id,
                session_id=session_id,
                role="user",
                message_type="query",
                content=question,
                status="completed",
            )
        )
        assistant_message = self.message_repository.create(
            Message(
                workspace_id=workspace_id,
                session_id=session_id,
                role="assistant",
                message_type="query_result",
                content=summary,
                status=query_status,
            )
        )
        self.prompt_record_repository.create(
            PromptRecord(
                assistant_message_id=assistant_message.id,
                system_prompt=prompt_input["system_prompt"],
                metadata_text=prompt_input["metadata"],
                user_question=prompt_input["question"],
            )
        )
        self.query_record_repository.create(
            QueryRecord(
                assistant_message_id=assistant_message.id,
                database_connection_id=connection.id,
                sql_query=sql_query,
                status=query_status,
                error_message=query_error_message,
                response_columns=result.columns if result else [],
                response_rows=result.rows if result else [],
                row_count=result.row_count if result else 0,
                execution_time_ms=result.execution_time_ms if result else 0,
                truncated=result.truncated if result else False,
            )
        )
        self.token_usage_repository.create(
            TokenUsage(
                message_id=assistant_message.id,
                workspace_id=workspace_id,
                session_id=session_id,
                provider=provider,
                model_name=model_name,
                stage="sql_generation",
                total_tokens=token_usage.total_tokens,
                input_tokens=token_usage.input_tokens,
                output_tokens=token_usage.output_tokens,
                cached_input_tokens=token_usage.cached_input_tokens,
            )
        )
        self.db.commit()

    def _load_previous_context(self, session_id: int) -> dict[str, str | None]:
        last_user_message = self.message_repository.get_last_user_query(session_id)
        last_query_record = self.query_record_repository.get_last_completed_for_session(session_id)
        return {
            "last_user_question": last_user_message.content if last_user_message else None,
            "last_sql_query": last_query_record.sql_query if last_query_record else None,
        }
