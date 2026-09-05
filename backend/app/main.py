from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from asgi_correlation_id import CorrelationIdMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from app.core import configure_logging, get_logger
from app.exceptions import (
    AgentRecursionLimitExceeded,
    DatabaseConnectionAlreadyExists,
    DatabaseConnectionNotFound,
    DatabaseMetadataNotReady,
    EncryptionKeyMissing,
    SQLExecutionFailed,
    SQLGenerationFailed,
    SQLGenerationTimedOut,
    RateLimitExceeded,
    RateLimitUnavailable,
    SessionAlreadyExists,
    SessionKeyMissing,
    SessionNotFound,
    UnsafeSQLQuery,
    WorkspaceAlreadyExists,
    WorkspaceKeyMissing,
    WorkspaceNotFound,
)
from app.middleware import RequestLoggingMiddleware
from app.routers.database_connection import router as database_connection_router
from app.routers.query import router as query_router
from app.routers.session import router as session_router
from app.routers.workspace import router as workspace_router

from app.db import ping_database

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")
configure_logging()
logger = get_logger(__name__)

app = FastAPI()
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CorrelationIdMiddleware)


@app.exception_handler(WorkspaceNotFound)
async def workspace_not_found_handler(request: Request, exc: WorkspaceNotFound):
    logger.warning("workspace.not_found", path=request.url.path)
    return JSONResponse(
        status_code=404,
        content={"detail": "Workspace not found"},
    )


@app.exception_handler(WorkspaceAlreadyExists)
async def workspace_already_exists_handler(request: Request, exc: WorkspaceAlreadyExists):
    logger.warning("workspace.already_exists", path=request.url.path)
    return JSONResponse(
        status_code=409,
        content={"detail": "Workspace already exists"},
    )


@app.exception_handler(WorkspaceKeyMissing)
async def workspace_key_missing_handler(request: Request, exc: WorkspaceKeyMissing):
    logger.warning("workspace.key_missing", path=request.url.path)
    return JSONResponse(
        status_code=400,
        content={"detail": "X-Workspace-Key header is required"},
    )


@app.exception_handler(SessionNotFound)
async def session_not_found_handler(request: Request, exc: SessionNotFound):
    logger.warning("session.not_found", path=request.url.path)
    return JSONResponse(
        status_code=404,
        content={"detail": "Session not found"},
    )


@app.exception_handler(SessionAlreadyExists)
async def session_already_exists_handler(request: Request, exc: SessionAlreadyExists):
    logger.warning("session.already_exists", path=request.url.path)
    return JSONResponse(
        status_code=409,
        content={"detail": "Session already exists"},
    )


@app.exception_handler(SessionKeyMissing)
async def session_key_missing_handler(request: Request, exc: SessionKeyMissing):
    logger.warning("session.key_missing", path=request.url.path)
    return JSONResponse(
        status_code=400,
        content={"detail": "X-Session-Key header is required"},
    )


@app.exception_handler(DatabaseConnectionAlreadyExists)
async def database_connection_already_exists_handler(
    request: Request,
    exc: DatabaseConnectionAlreadyExists,
):
    logger.warning("database_connection.already_exists", path=request.url.path)
    return JSONResponse(
        status_code=409,
        content={"detail": "Session already has a different successful database connection"},
    )


@app.exception_handler(EncryptionKeyMissing)
async def encryption_key_missing_handler(request: Request, exc: EncryptionKeyMissing):
    logger.error("database_connection.encryption_key_missing_or_invalid", path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Database connection encryption key is missing or invalid"},
    )
    
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(
        "request.validation_failed",
        path=request.url.path,
        error_count=len(exc.errors()),
    )
    errors = []
    
    for error in exc.errors():
        field = ".".join(str(x) for x in error["loc"][1:]) if len(error["loc"]) > 1 else ".".join(str(x) for x in error["loc"])
        
        errors.append({
            "field": field,
            "message": error["msg"].capitalize(),
            "type": error["type"]
        })
        
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Validation failed for one or more fields.",
            "errors": errors
        }
    )

class Health(BaseModel):
    message: str

class DatabaseHealth(BaseModel):
    connected: bool

@app.get("/healthy", response_model=Health)
async def healthy() -> Health:
    return Health(message="Service is healthy")

@app.get("/db/healthy", response_model=DatabaseHealth)
def database_healthy() -> DatabaseHealth:
    return DatabaseHealth(connected=ping_database())

@app.exception_handler(DatabaseConnectionNotFound)
async def database_connection_not_found_handler(
    request: Request,
    exc: DatabaseConnectionNotFound,
):
    logger.warning("database_connection.not_found", path=request.url.path)
    return JSONResponse(
        status_code=404,
        content={"detail": "No successful database connection found for this session"},
    )


@app.exception_handler(DatabaseMetadataNotReady)
async def database_metadata_not_ready_handler(
    request: Request,
    exc: DatabaseMetadataNotReady,
):
    logger.warning("database_metadata.not_ready", path=request.url.path)
    return JSONResponse(
        status_code=409,
        content={"detail": "Database metadata is not ready for querying"},
    )


@app.exception_handler(UnsafeSQLQuery)
async def unsafe_sql_query_handler(request: Request, exc: UnsafeSQLQuery):
    logger.warning("query.unsafe_sql", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


@app.exception_handler(SQLGenerationFailed)
async def sql_generation_failed_handler(request: Request, exc: SQLGenerationFailed):
    logger.error("query.generation_failed", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=502,
        content={"detail": str(exc)},
    )


@app.exception_handler(SQLGenerationTimedOut)
async def sql_generation_timed_out_handler(request: Request, exc: SQLGenerationTimedOut):
    logger.error("query.generation_timed_out", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=504,
        content={"detail": str(exc)},
    )


@app.exception_handler(AgentRecursionLimitExceeded)
async def agent_recursion_limit_exceeded_handler(
    request: Request,
    exc: AgentRecursionLimitExceeded,
):
    logger.error("query.agent_recursion_limit_exceeded", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=502,
        content={"detail": str(exc)},
    )


@app.exception_handler(SQLExecutionFailed)
async def sql_execution_failed_handler(request: Request, exc: SQLExecutionFailed):
    logger.warning("query.execution_failed", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(
        "rate_limit.exceeded",
        path=request.url.path,
        retry_after_seconds=exc.retry_after_seconds,
    )
    return JSONResponse(
        status_code=429,
        content={"detail": str(exc), "retry_after_seconds": exc.retry_after_seconds},
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )


@app.exception_handler(RateLimitUnavailable)
async def rate_limit_unavailable_handler(request: Request, exc: RateLimitUnavailable):
    logger.error("rate_limit.unavailable", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
    )

app.include_router(workspace_router)
app.include_router(session_router)
app.include_router(database_connection_router)
app.include_router(query_router)
