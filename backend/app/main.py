from pathlib import Path
import json

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from app.exceptions import (
    SessionAlreadyExists,
    SessionNotFound,
    WorkspaceAlreadyExists,
    WorkspaceNotFound,
)
from app.routers.session import router as session_router
from app.routers.workspace import router as workspace_router

from app.db import ping_database

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

app = FastAPI()


@app.exception_handler(WorkspaceNotFound)
async def workspace_not_found_handler(request: Request, exc: WorkspaceNotFound):
    return JSONResponse(
        status_code=404,
        content={"detail": "Workspace not found"},
    )


@app.exception_handler(WorkspaceAlreadyExists)
async def workspace_already_exists_handler(request: Request, exc: WorkspaceAlreadyExists):
    return JSONResponse(
        status_code=409,
        content={"detail": "Workspace already exists"},
    )


@app.exception_handler(SessionNotFound)
async def session_not_found_handler(request: Request, exc: SessionNotFound):
    return JSONResponse(
        status_code=404,
        content={"detail": "Session not found"},
    )


@app.exception_handler(SessionAlreadyExists)
async def session_already_exists_handler(request: Request, exc: SessionAlreadyExists):
    return JSONResponse(
        status_code=409,
        content={"detail": "Session already exists"},
    )
    
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
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
    
class QueryRequest(BaseModel):
    question: str
    
class QueryResponse(BaseModel):
    sql_query: str


llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0.7
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant that translates natural language to SQL queries."),
    ("user", "{question}")
])

chain = prompt | llm

@app.get("/healthy", response_model=Health)
async def healthy() -> Health:
    return Health(message="Service is healthy")

@app.get("/db/healthy", response_model=DatabaseHealth)
def database_healthy() -> DatabaseHealth:
    return DatabaseHealth(connected=ping_database())

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    response = chain.invoke({"question": request.question})
    return QueryResponse(sql_query=response.content)

def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    async def generate():
        async for chunk in chain.astream({"question": request.question}):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            
            if content:
                yield sse_event("message", {
                    "content": content,
                    "finish": False
                })
                
        yield sse_event("message", {
            "content": content,
            "finish": True
        })
                
    return StreamingResponse(
        generate(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

app.include_router(workspace_router)
app.include_router(session_router)
