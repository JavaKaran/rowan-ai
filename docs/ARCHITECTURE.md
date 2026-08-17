# AI SQL Query Engine Architecture

## High-Level Architecture

```text
                    Next.js Frontend
                           │
                           ▼
                     FastAPI API
                           │
                           ▼
                  Workspace / Session Layer
                           │
                           ▼
                     Query Orchestrator
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
  Schema Retrieval     SQL Agent         Query Persistence
      Tools         (LangChain Agent)       and Tracing
        │                  │
        └────────────┬─────┘
                     ▼
          After Guardrail + Repair Loop
                     │
                     ▼
                 SQL Executor
                     │
                     ▼
            Connected User Database
```

## Core Design Shift

This project should no longer be described as a single prompt in, single SQL out system.

The target implementation is an agentic SQL generation pipeline with:

- A LangChain agent instead of a single LLM invoke
- Tool-driven schema retrieval per question
- A bounded repair loop before execution
- An evaluation harness that measures quality and reliability

## Query Lifecycle

```text
POST /query
   ↓
Load workspace and session context
   ↓
Load active database connection
   ↓
Create LangChain agent with schema tools
   ↓
Agent retrieves only relevant schema context
   ↓
Generate SQL candidate
   ↓
Run after guardrail
   ↓
If blocked, repair and retry
   ↓
Maximum 3 total attempts
   ↓
Execute approved SQL
   ↓
Persist result, attempts, latency, and token usage
   ↓
Return response
```

## Repair Loop

The query path should follow this bounded loop:

```text
Generate
  ↓
After Guardrail
  ├── pass    → Execute
  └── block   → Repair
                 ↓
               After Guardrail
                 ├── pass    → Execute
                 └── block   → Retry until 3 total attempts
```

Rules:

- Attempt 1 is the initial generation
- Attempts 2 and 3 are repair attempts
- After-guardrail failures should be fed back into the agent as structured repair context
- If all 3 attempts fail, return a typed generation failure with captured reasons

## Schema Retrieval Architecture

The model should not receive the entire database metadata blob for every question.

Instead, the agent should retrieve only relevant schema context via tool calling. The retrieval layer should expose tools for:

- Relevant tables
- Columns and types for selected tables
- Relationships and join paths between tables
- Optional lightweight statistics later

Recommended flow:

1. User asks a question.
2. Agent decides which schema retrieval tools to call.
3. Tools return only the tables, columns, and relationships needed for that question.
4. Agent generates SQL using that scoped context.

Benefits:

- Smaller prompts
- Lower token usage
- Better relevance
- Less confusion from unrelated tables
- Better scaling on large schemas

## Major Components

### Query Orchestrator

Responsibilities:

- Own the end-to-end query workflow
- Initialize agent execution state
- Coordinate before guardrails, generation, after guardrails, repair, and execution
- Persist every attempt and final outcome

### LangChain Agent Layer

Responsibilities:

- Interpret the user question
- Call schema retrieval tools
- Generate SQL candidates
- Consume guardrail feedback during repair attempts

This layer should be documented as an agent runtime, not a thin wrapper around a single `invoke`.

### Before Guardrail

Responsibilities:

- Inspect the incoming natural language request before agent execution
- Block prompt injection, jailbreak attempts, and write-intent requests
- Normalize or annotate safe requests for downstream execution

This replaces the old manual pre-generation guard checks with a LangChain-compatible before guardrail.

### Schema Retrieval Tools

Responsibilities:

- Retrieve relevant tables for a question
- Retrieve columns and types for selected tables
- Retrieve foreign keys and relationships
- Return compact structured outputs the agent can reason over

The retrieval system should be backed by cached metadata, but the model should only see the subset returned by tools.

### After Guardrail

Responsibilities:

- Enforce read-only behavior
- Reject unsafe statements and patterns
- Check schema usage against retrieved metadata
- Emit machine-readable guardrail failures for repair

This replaces the old manual SQL validator framing with a LangChain-compatible after guardrail that runs on generated SQL before execution.

### Repair Engine

Responsibilities:

- Convert after-guardrail or execution failures into repair feedback
- Re-invoke the agent with the previous SQL and failure reason
- Stop after 3 total attempts

### SQL Executor

Responsibilities:

- Run only validated SQL
- Enforce timeouts and row limits
- Normalize rows for API responses
- Separate execution failures from generation failures

### Evaluation Harness

Responsibilities:

- Run a representative benchmark set of natural language questions
- Compare produced SQL or results against expected outcomes
- Track repair frequency, latency, token usage, and failure reasons

## Metadata Strategy

The system should still maintain a metadata cache for each connected database, but that cache now supports retrieval rather than prompt stuffing.

Application metadata store:

- Database connections
- Cached schema metadata
- Sessions
- Query history
- Attempt logs
- Token usage
- Evaluation runs

User database:

- Business data queried by the agent
- Never stores application state

## Observability

The architecture should persist enough detail to debug agent behavior:

- Initial SQL candidate
- Before-guardrail outcomes
- After-guardrail failures
- Repair attempts
- Final SQL
- Tool calls used for schema retrieval
- Execution time
- Token usage by attempt
- Final status: success, repaired success, before-guardrail block, after-guardrail block, execution failure

## Security

The system remains read-only by default.

Reject:

- `INSERT`
- `UPDATE`
- `DELETE`
- `ALTER`
- `DROP`
- `TRUNCATE`
- Multi-statement SQL
- Sensitive column access where applicable

The repair loop must never bypass the after guardrail. Every attempt must pass the after guardrail before execution.

Database

Future

FastAPI

↓

LangGraph

↓

Supervisor

↓

SQL Agent

↓

Visualization Agent

↓

Summary Agent

↓

Database
