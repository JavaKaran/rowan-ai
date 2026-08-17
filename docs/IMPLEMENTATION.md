# IMPLEMENTATION.md

> Backend-first implementation roadmap for the production-oriented AI SQL Query Engine

---

## 1. Target Runtime Architecture

```text
Frontend
   │
   ▼
FastAPI REST API
   │
   ▼
Workspace + Session Resolution
   │
   ▼
Query Orchestrator
   │
   ├───────────────┬────────────────┬─────────────────┐
   │               │                │                 │
   ▼               ▼                ▼                 ▼
Agent Runtime   Schema Tools   After Guardrail   Attempt Persistence
   │               │                │
   └───────────────┴──────────┬─────┘
                              ▼
                         Repair Loop
                              │
                              ▼
                          SQL Executor
                              │
                              ▼
                        Connected Database
```

This implementation plan assumes the SQL path is agentic, tool-driven, and explicitly retry-aware.

---

## 2. Desired Backend Structure

```text
backend/app/
├── routers/
│   └── query.py
├── services/
│   ├── query.py
│   ├── query_agent.py
│   ├── query_repair.py
│   ├── query_guardrails.py
│   ├── query_executor.py
│   ├── schema_retrieval.py
│   ├── database_metadata.py
│   └── evaluation_harness.py
├── repositories/
│   ├── query_record.py
│   ├── prompt_record.py
│   ├── token_usage.py
│   ├── database_metadata.py
│   └── evaluation_run.py
├── models/
│   ├── query_record.py
│   ├── prompt_record.py
│   ├── token_usage.py
│   ├── database_metadata.py
│   └── evaluation_run.py
└── schemas/
    ├── query.py
    └── evaluation.py
```

The exact file layout can evolve, but the docs should reflect these responsibilities:

- `query_agent.py`: LangChain agent construction and invocation
- `schema_retrieval.py`: tool definitions and retrieval logic
- `query_guardrails.py`: before and after guardrail definitions
- `query_repair.py`: repair loop coordination and structured retry inputs
- `evaluation_harness.py`: offline benchmark runner and metrics reporting

---

## 3. Implementation Principles

### LangChain Agent, Not Single Invoke

Replace the current single-call generation model with a LangChain agent that can:

- Decide when to inspect schema context
- Call retrieval tools
- Produce SQL candidates
- Accept structured guardrail feedback on retry attempts

The docs should treat agent execution as a workflow, not as prompt formatting plus one LLM response.

### Retrieval Over Metadata Dumping

Do not serialize full database metadata into every prompt.

Instead:

- Keep full metadata cached server-side
- Expose retrieval tools to the agent
- Return only relevant tables, columns, and relationships for the current question

### Guardrail-Driven Repair Loop

Every query run should follow:

1. Generate SQL
2. Run after guardrail
3. Repair if needed
4. Re-run after guardrail
5. Execute only after the after guardrail passes

Maximum attempts: `3`

### Evaluation Is a First-Class Deliverable

The project is not complete when the happy path works manually. It should include repeatable evaluation on representative workloads.

---

## 4. Milestones

### Milestone 1: Core Backend Foundation

Tasks:

- FastAPI app structure
- SQLAlchemy and Alembic setup
- Logging and error model
- Workspace and session resolution
- Database connection management

Deliverable:

A stable backend foundation that can resolve database and session context for each query.

### Milestone 2: Metadata Cache and Retrieval Substrate

Tasks:

- Introspect connected databases
- Cache tables, columns, foreign keys, and relationships
- Design retrieval-friendly metadata access methods
- Separate metadata storage from model-facing context

Deliverable:

A metadata layer that supports retrieval-time lookups without passing the full schema to the model.

### Milestone 3: Schema Retrieval Tools

Tasks:

- Build a `find_relevant_tables` tool
- Build a `get_table_columns` tool
- Build a `get_table_relationships` tool
- Return compact structured payloads for agent use

Deliverable:

Tool-calling schema access for each question.

### Milestone 4: LangChain Agent Runtime

Tasks:

- Replace single invoke generation with an agent
- Attach schema retrieval tools
- Add a before guardrail for user-input screening
- Add prompt instructions for read-only SQL generation
- Capture agent traces and tool calls

Deliverable:

An agent that can reason over user questions and gather schema context before writing SQL.

### Milestone 5: Guardrails and Repair Loop

Tasks:

- Replace manual guardrails with LangChain before and after guardrails
- Keep strict read-only and schema-usage enforcement in the after guardrail
- Convert after-guardrail failures into structured repair feedback
- Add retry loop with a maximum of 3 attempts
- Distinguish before-guardrail blocks, after-guardrail blocks, and execution failures

Deliverable:

A bounded generate-guardrail-repair workflow.

### Milestone 6: Execution and Persistence

Tasks:

- Execute only validated SQL
- Enforce timeout and row caps
- Persist each attempt, not just the final SQL
- Persist tool calls, guardrail outcomes, latency, and token usage

Deliverable:

A debuggable production-style query execution path.

### Milestone 7: Evaluation Harness

Tasks:

- Create 50 to 100 representative benchmark questions
- Define expected outputs or acceptance rules
- Run benchmark queries automatically
- Record accuracy, repair rate, latency, token usage, and failure modes

Deliverable:

A repeatable benchmark suite that demonstrates engineering rigor.

---

## 5. Query Pipeline

```text
User Question
   ↓
Resolve Workspace / Session / Connection
   ↓
Start Attempt 1
   ↓
LangChain Agent
   ↓
Tool Calls for Relevant Schema
   ↓
Generate SQL Candidate
   ↓
Run After Guardrail
   ├── Pass → Execute
   └── Block → Repair Attempt
                ↓
              Run After Guardrail Again
                ├── Pass → Execute
                └── Block → Retry until 3 attempts total
```

Important rules:

- Execution never happens before the after guardrail passes
- Full metadata never goes directly into the model prompt by default
- Repair feedback should include the prior SQL and the exact guardrail failure

---

## 6. Schema Retrieval Design

The retrieval layer should answer question-scoped schema needs.

Suggested tool surface:

- `find_relevant_tables(question, workspace_id, session_id)`
- `get_columns(table_names)`
- `get_relationships(table_names)`

Expected behavior:

- The agent first narrows candidate tables
- The agent then asks for columns only on likely tables
- The agent asks for relationships only where joins are needed

This keeps context small and intentional.

---

## 7. Repair Loop Design

The repair loop should be explicit rather than implicit, and it should be driven by guardrail outcomes.

Suggested repair input:

- Original user question
- Previous SQL candidate
- Guardrail failure category
- Human-readable error detail
- Attempt count remaining

Suggested failure categories:

- Before-guardrail blocked request
- Unsafe SQL
- Unknown table
- Unknown column
- Missing limit
- Multi-statement output
- Sensitive field access
- Execution error

The repair prompt should instruct the agent to minimally modify the prior SQL to satisfy the reported guardrail constraint.

---

## 8. Evaluation Harness Design

The evaluation suite should cover both simple and realistic questions.

Dataset composition:

- Single-table filtering
- Aggregations
- Group by and order by
- Time-based analytics
- Multi-table joins
- Follow-up conversational queries
- Ambiguous questions
- Invalid or unsafe user requests

Metrics:

- Accuracy
- Repair rate
- Average attempts per successful query
- Latency
- Token usage
- Failure mode distribution

Success criteria should be documented per query, either as:

- Exact SQL match where appropriate
- Result equivalence
- Rule-based acceptance checks

---

## 9. Non-Goals for This Phase

Not required for the first production-worthy version:

- Fully autonomous multi-step business analysis
- Fine-tuning
- Cross-database federated querying
- Write-capable SQL agents

The focus is correctness, safety, retrieval quality, and observability.
