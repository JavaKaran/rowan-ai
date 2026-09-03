from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_session_key, get_workspace_key
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
from app.schemas import QueryRequest, QueryResponse
from app.services.query import QueryService
from app.services.database_connection_runtime import DatabaseConnectionRuntime
from app.services.query_agent import create_query_agent
from app.services.query_executor import SQLQueryExecutor
from app.services.query_guardrails import AfterGuardrail, BeforeGuardrail
from app.services.query_prompt_builder import QueryPromptBuilder
from app.services.query_repair import QueryRepairLoop

router = APIRouter(prefix="/query", tags=["query"])


def get_query_service(db: Session = Depends(get_db)) -> QueryService:
    return QueryService(
        db=db,
        connection_repository=DatabaseConnectionRepository(db),
        metadata_repository=DatabaseMetadataRepository(db),
        session_repository=SessionRepository(db),
        workspace_repository=WorkspaceRepository(db),
        message_repository=MessageRepository(db),
        prompt_record_repository=PromptRecordRepository(db),
        query_record_repository=QueryRecordRepository(db),
        token_usage_repository=TokenUsageRepository(db),
        prompt_builder=QueryPromptBuilder(),
        before_guardrail=BeforeGuardrail(),
        repair_loop=QueryRepairLoop(
            query_agent=create_query_agent(),
            after_guardrail=AfterGuardrail(),
        ),
        query_executor=SQLQueryExecutor(connection_runtime=DatabaseConnectionRuntime()),
    )


@router.post("/", response_model=QueryResponse)
def run_query(
    payload: QueryRequest,
    workspace_key: str = Depends(get_workspace_key),
    session_key: str = Depends(get_session_key),
    service: QueryService = Depends(get_query_service),
) -> QueryResponse:
    result = service.run_query(
        workspace_key=workspace_key,
        session_key=session_key,
        question=payload.question,
    )
    return QueryResponse.model_validate(result.model_dump())
