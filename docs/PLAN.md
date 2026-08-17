# AI SQL Query Engine

> Planning Document (v3)

---

## 1. Goal

Build an AI-powered SQL Query Engine that feels closer to a real engineering system than a demo.

The project should:

- Accept natural language questions about relational data
- Use a LangChain agent instead of a one-shot LLM call
- Retrieve only relevant schema context through tool calling
- Repair invalid SQL in a bounded loop
- Execute only validated read-only SQL
- Use LangChain before and after guardrails instead of manual guardrails
- Persist traces, attempts, and usage metrics
- Include an evaluation harness with representative benchmark queries

This project is intended to be interview-worthy and engineering-worthy, not just functionally correct on a few hand-tested examples.

---

## 2. What Changes from the Simpler Version

The simpler approach was:

- Send large schema metadata into the model prompt
- Generate SQL in one invoke
- Validate once
- Execute if valid

The target approach is:

- Use a LangChain agent
- Let the agent retrieve schema context through tools
- Run a before guardrail → generate → after guardrail → repair → after guardrail → execute pipeline
- Stop after 3 total attempts
- Evaluate performance on a benchmark set of 50 to 100 queries

This shift matters because realistic schemas, safety requirements, and reliability expectations are not well served by a one-shot prompt pipeline.

---

## 3. Product Requirements

### Agent Runtime

The system must use a LangChain agent rather than a single model invocation.

The agent should be able to:

- Understand the question
- Pass through a before guardrail for request screening
- Decide which schema retrieval tools to call
- Generate SQL
- Consume repair feedback when an after-guardrail or execution step fails

### Repair Loop

The SQL generation lifecycle should be:

```text
Before Guardrail
  ↓
Generate
  ↓
After Guardrail
  ↓
Repair if needed
  ↓
After Guardrail again
  ↓
Execute
```

Constraints:

- Maximum 3 total attempts
- Attempt 1 is generation
- Attempts 2 and 3 are repairs
- No SQL may execute unless the after guardrail passes

### Schema Retrieval

Do not provide the entire database metadata to the model.

Instead, the agent should retrieve relevant:

- Tables
- Columns
- Relationships

for each question using tool calling backed by cached metadata.

### Evaluation Harness

The project must include a benchmark suite of roughly 50 to 100 representative queries and report:

- Accuracy
- Repair rate
- Latency
- Tokens
- Failure modes

---

## 4. Design Objectives

Primary objectives:

- Demonstrate LangChain agent architecture
- Demonstrate before and after guardrail integration
- Demonstrate tool-calling based retrieval
- Demonstrate safe SQL generation patterns
- Demonstrate reliability through repair and evaluation
- Demonstrate backend engineering discipline

Secondary objectives:

- Remain easy to explain in interviews
- Be small enough to complete
- Leave room for future observability and product polish

---

## 5. Core Architecture Concept

The root abstraction is still a workspace.

Each workspace owns:

- Database connection
- Cached schema metadata
- Sessions
- Query history
- Attempt logs
- Token usage
- Evaluation runs

Every request should resolve:

- Workspace
- Session
- Active connection
- Metadata cache

The difference is how metadata is used:

- The cache remains full-fidelity server-side
- The model only sees question-relevant slices retrieved by tools

---

## 6. High-Level Query Flow

```text
User Question
   ↓
Resolve Workspace / Session / Connection
   ↓
Create Agent Runtime
   ↓
Agent Calls Schema Retrieval Tools
   ↓
Generate SQL Candidate
   ↓
Run After Guardrail
   ├── Pass → Execute
   └── Block → Repair
                ↓
              Run After Guardrail Again
                ├── Pass → Execute
                └── Block → Retry until 3 attempts total
```

Persist for each query:

- User question
- Tool calls
- SQL per attempt
- Before-guardrail outcomes
- After-guardrail outcomes
- Final execution result
- Latency
- Token usage
- Final status

---

## 7. Technical Direction

### Backend

- FastAPI
- LangChain
- SQLAlchemy
- Alembic
- PostgreSQL for application state

### User Databases

Initial support:

- SQLite
- PostgreSQL
- MySQL

### Optional Additions Later

- LangSmith
- OpenTelemetry
- Redis
- `sqlglot`

---

## 8. MVP Definition

The MVP is complete when the system can:

- Connect to a supported database
- Cache schema metadata
- Retrieve relevant schema context through tools
- Use a LangChain agent to generate SQL
- Use before and after guardrails to enforce request and SQL safety
- Repair invalid SQL up to 3 attempts
- Execute safe validated SQL
- Persist traces and metrics
- Run an evaluation harness over 50 to 100 benchmark questions

The MVP is not complete if it only works in ad hoc manual demos.

---

## 9. Benchmark Expectations

The benchmark set should include:

- Simple lookups
- Filters and sorting
- Aggregations
- Grouping
- Date and time queries
- Multi-table joins
- Follow-up conversational queries
- Ambiguous questions
- Unsafe requests that must be rejected

Suggested reporting:

- Overall accuracy
- Accuracy before repair
- Accuracy after repair
- Percentage of queries needing repair
- Average latency per query
- Average token usage per query
- Most common failure categories

---

## 10. Success Criteria

This project will feel engineering-worthy if the docs and implementation show:

- Agent-based architecture instead of single invoke prompting
- Retrieval instead of prompt stuffing
- Explicit bounded repair behavior
- Measurable quality through benchmark evaluation
- Enough observability to debug failures

That combination is what turns this from a simple AI demo into a stronger systems project.

---

## 11. Phase-Wise Implementation Task List

This reflects the actual current state of `backend/` against the target architecture. Today the pipeline is still the "simpler version" from Section 2: full metadata dumped into one prompt (`query_prompt_builder.py`), a single LLM invoke (`query_llm.py`), one regex-based validation pass (`query_validator.py`), then execute. Foundation and execution/persistence plumbing already exist and are reused, not rebuilt.

### Phase 0 — Foundation (done)

Goal: confirm the substrate the rest of the plan builds on is solid.

- FastAPI app, SQLAlchemy models, Alembic migrations
- Workspace / session / database connection resolution
- Metadata introspection and caching (`database_metadata.py`, `metadata_jobs.py`)
- SQL executor with timeout/row limits (`query_executor.py`)
- Per-turn persistence of question, SQL, tokens (`query.py`, message/query/prompt/token repositories)

Checkpoint: no new work here — used as-is by later phases.

### Phase 1 — Schema Retrieval Tools

Goal: stop serializing full metadata into the prompt; expose it as tool-callable, question-scoped retrieval.

- Add `schema_retrieval.py` service with three tools backed by the existing metadata cache:
  - `find_relevant_tables(question)`
  - `get_columns(table_names)`
  - `get_relationships(table_names)`
- Each tool returns compact structured output (table/column/FK subsets), not the full blob
- Keep `database_metadata.py` as the full-fidelity cache; tools read from it, they don't replace it

Checkpoint: given a question, the three tools return correct scoped subsets on a schema with 10+ tables, verified with unit tests against the metadata cache directly (no LLM involved yet).

### Phase 2 — LangChain Agent Runtime

Goal: replace the single `chain.invoke()` in `query_llm.py` with an agent that decides which retrieval tools to call before producing SQL.

- Add `query_agent.py`: LangChain agent bound to the Phase 1 tools, producing the same `sql_query` / `summary` / token usage shape `query_llm.py` returns today
- Preserve session context (last question, last SQL) as part of agent input
- Capture and expose tool-call trace (which tools, what args, what came back) for later persistence
- Swap `query.py` to call the agent instead of `LangChainGroqQueryLLMClient` directly

Checkpoint: for a sample of questions, the agent calls `find_relevant_tables` before generating SQL, uses only columns it retrieved, and produces valid SQL without the full schema ever entering the prompt. Manual run through `/query` still works end-to-end.

### Phase 3 — Guardrails as LangChain Components

Goal: keep the existing safety checks in `query_validator.py` but restructure them into an explicit before/after guardrail split with machine-readable failure output (not just raised exceptions).

- `query_guardrails.py`:
  - Before guardrail: request screening (prompt injection, write-intent) — reuses today's `validate_user_request` logic
  - After guardrail: SQL safety (read-only, known tables/columns, sensitive columns, LIMIT) — reuses today's `validate` logic
- After guardrail returns a typed failure (category + detail) instead of raising directly, so Phase 4 can consume it
- Before guardrail still raises immediately — a blocked request never reaches the agent

Checkpoint: existing validator test cases pass unchanged in behavior; after-guardrail failures are now inspectable structured objects, not just exception strings.

### Phase 4 — Repair Loop

Goal: bound retries at 3 total attempts, feeding after-guardrail failures back into the agent instead of failing the whole request on first block.

- `query_repair.py`: given previous SQL + guardrail failure category/detail + attempts remaining, re-invoke the agent with repair instructions to minimally fix the prior SQL
- `query.py` orchestration becomes: before guardrail → generate (attempt 1) → after guardrail → [repair → after guardrail] × up to 2 more attempts → execute or typed failure
- Execution never runs until an attempt passes the after guardrail; if all 3 attempts fail, return a typed generation failure with captured per-attempt reasons

Checkpoint: a deliberately malformed question (e.g. referencing a wrong column name) is not fixed on attempt 1 but succeeds by attempt 2 or 3, and this is visible in the response/logs as a "repaired success."

### Phase 5 — Attempt-Level Observability & Persistence

Goal: persist what Section 6 requires — not just the final SQL, but every attempt.

- Extend query/attempt persistence to store per-attempt: SQL candidate, before/after guardrail outcomes, tool calls used, latency, token usage
- Final `QueryRecord` status distinguishes: success, repaired success, before-guardrail block, after-guardrail block, execution failure
- Surface attempt count and repair reason in the API response for debuggability

Checkpoint: for a repaired query, querying the DB after the fact shows all 2-3 attempts with their individual guardrail outcomes, not just the final one.

### Phase 6 — Evaluation Harness

Goal: make quality measurable instead of anecdotal.

- `evaluation_harness.py`: runs a fixed benchmark set against the live pipeline
- Benchmark dataset (50-100 questions) covering: simple lookups, filters/sorting, aggregations, grouping, date/time, multi-table joins, follow-up conversational queries, ambiguous questions, unsafe requests
- Acceptance rules per question: exact SQL match, result equivalence, or rule-based check
- Report: overall accuracy, accuracy before/after repair, % needing repair, avg attempts, avg latency, avg tokens, failure category breakdown

Checkpoint: harness runs unattended end-to-end and produces a report; MVP (Section 8) is considered complete once this report is generated and reviewed against Section 9's expectations.

