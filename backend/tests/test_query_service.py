import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.fernet import Fernet
from sqlalchemy.exc import SQLAlchemyError

from app.core.database_connections import encrypt_password
from app.exceptions import (
    DatabaseConnectionNotFound,
    DatabaseMetadataNotReady,
    SQLExecutionFailed,
    UnsafeSQLQuery,
)
from app.services.query import QueryService
from app.schemas import QueryResponse, QueryTokenUsage
from app.services.query_executor import SQLQueryExecutor
from app.services.query_prompt_builder import QueryPromptBuilder
from app.services.query_validator import ReadOnlySQLValidator


class QueryPromptBuilderTest(unittest.TestCase):
    def test_build_formats_relevant_metadata(self):
        builder = QueryPromptBuilder()

        prompt_input = builder.build(
            system_prompt="Custom system prompt",
            metadata_json={
                "database_type": "postgresql",
                "database_name": "analytics",
                "schemas": [
                    {
                        "name": "public",
                        "tables": [
                            {
                                "name": "users",
                                "primary_key": ["id"],
                                "columns": [
                                    {"name": "id", "type": "INTEGER"},
                                    {"name": "email", "type": "VARCHAR"},
                                ],
                                "foreign_keys": [],
                            },
                            {
                                "name": "orders",
                                "primary_key": ["id"],
                                "columns": [
                                    {"name": "id", "type": "INTEGER"},
                                    {"name": "user_id", "type": "INTEGER"},
                                    {
                                        "name": "status",
                                        "type": "uploadstatus",
                                        "enum_values": ["PENDING", "COMPLETED", "FAILED"],
                                    },
                                    {
                                        "name": "payload",
                                        "type": "JSONB",
                                        "json_kind": "jsonb",
                                    },
                                    {
                                        "name": "tags",
                                        "type": "VARCHAR[]",
                                        "array_item_type": "VARCHAR",
                                    },
                                ],
                                "foreign_keys": [
                                    {
                                        "columns": ["user_id"],
                                        "referred_schema": "public",
                                        "referred_table": "users",
                                        "referred_columns": ["id"],
                                    }
                                ],
                            },
                        ],
                    }
                ],
                "relationships": [
                    {
                        "from_schema": "public",
                        "from_table": "orders",
                        "from_columns": ["user_id"],
                        "to_schema": "public",
                        "to_table": "users",
                        "to_columns": ["id"],
                    }
                ],
            },
            question="List recent orders",
        )

        self.assertEqual(prompt_input["system_prompt"], "Custom system prompt")
        self.assertIn("database_name: analytics", prompt_input["metadata"])
        self.assertIn("table: users", prompt_input["metadata"])
        self.assertIn("columns: id (INTEGER), email (VARCHAR)", prompt_input["metadata"])
        self.assertIn(
            "status (uploadstatus; allowed: PENDING, COMPLETED, FAILED)",
            prompt_input["metadata"],
        )
        self.assertIn("payload (JSONB; jsonb document)", prompt_input["metadata"])
        self.assertIn("tags (VARCHAR[]; array items: VARCHAR)", prompt_input["metadata"])
        self.assertIn("foreign_keys: user_id -> public.users(id)", prompt_input["metadata"])
        self.assertIn("public.orders(user_id) -> public.users(id)", prompt_input["metadata"])
        self.assertEqual(prompt_input["question"], "List recent orders")


class ReadOnlySQLValidatorTest(unittest.TestCase):
    def setUp(self):
        self.validator = ReadOnlySQLValidator()

    def test_accepts_single_select(self):
        validated = self.validator.validate("SELECT id, email FROM users;")
        self.assertEqual(validated, "SELECT id, email FROM users")

    def test_accepts_cte(self):
        validated = self.validator.validate(
            "WITH recent AS (SELECT id FROM users) SELECT * FROM recent"
        )
        self.assertTrue(validated.startswith("WITH recent"))

    def test_rejects_multiple_statements(self):
        with self.assertRaises(UnsafeSQLQuery):
            self.validator.validate("SELECT 1; SELECT 2;")

    def test_rejects_mutating_keywords(self):
        with self.assertRaises(UnsafeSQLQuery):
            self.validator.validate("DELETE FROM users")

    def test_rejects_non_select_statement(self):
        with self.assertRaises(UnsafeSQLQuery):
            self.validator.validate("SHOW TABLES")

    def test_rejects_comments(self):
        with self.assertRaises(UnsafeSQLQuery):
            self.validator.validate("SELECT * FROM users -- comment")


class SQLAlchemyQueryExecutorTest(unittest.TestCase):
    def setUp(self):
        self.original_key = os.environ.get("DATABASE_CONNECTION_ENCRYPTION_KEY")
        os.environ["DATABASE_CONNECTION_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
        self.connection = SimpleNamespace(
            database_type="postgresql",
            username="user",
            encrypted_password=encrypt_password("secret"),
            host="localhost",
            port=5432,
            database_name="app_db",
            ssl_mode="prefer",
        )

    def tearDown(self):
        if self.original_key is None:
            os.environ.pop("DATABASE_CONNECTION_ENCRYPTION_KEY", None)
        else:
            os.environ["DATABASE_CONNECTION_ENCRYPTION_KEY"] = self.original_key

    def test_execute_normalizes_rows_and_truncates(self):
        runtime = FakeConnectionRuntime(
            FakeEngine(
                FakeDBConnection(
                rows=[
                    FakeRow({"id": 1, "name": "Ada"}),
                    FakeRow({"id": 2, "name": "Grace"}),
                    FakeRow({"id": 3, "name": "Linus"}),
                ],
                keys=["id", "name"],
                )
            )
        )
        executor = SQLQueryExecutor(
            connection_runtime=runtime,
            max_rows=2,
            statement_timeout_ms=5000,
        )

        result = executor.execute(self.connection, "SELECT id, name FROM users")

        self.assertEqual(result.columns, ["id", "name"])
        self.assertEqual(result.rows, [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Grace"}])
        self.assertEqual(result.row_count, 2)
        self.assertTrue(result.truncated)
        self.assertGreaterEqual(result.execution_time_ms, 0)
        self.assertEqual(runtime.engine.connection.commands[0][0], "SET statement_timeout = :timeout_ms")

    def test_execute_raises_domain_error_on_database_failure(self):
        executor = SQLQueryExecutor(
            connection_runtime=FakeConnectionRuntime(FakeEngine(FailingDBConnection()))
        )

        with self.assertRaises(SQLExecutionFailed):
            executor.execute(self.connection, "SELECT 1")


class QueryServiceTest(unittest.TestCase):
    def test_run_query_happy_path(self):
        prompt_builder = QueryPromptBuilder()
        llm_client = FakeLLMClient(
            sql_query="SELECT id FROM users LIMIT 10",
            summary="Fetches user IDs with a result cap for safe browsing.",
            token_usage=QueryTokenUsage(
                total_tokens=120,
                input_tokens=90,
                output_tokens=30,
                cached_input_tokens=12,
            ),
        )
        validator = FakeValidator("SELECT id FROM users LIMIT 10")
        executor = FakeExecutor(
            QueryResponse(
                sql_query="SELECT id FROM users LIMIT 10",
                summary="",
                columns=["id"],
                rows=[{"id": 1}],
                row_count=1,
                execution_time_ms=12,
                truncated=False,
                token_usage=QueryTokenUsage(
                    total_tokens=0,
                    input_tokens=0,
                    output_tokens=0,
                    cached_input_tokens=0,
                ),
            )
        )
        service = QueryService(
            db=FakeDB(),
            connection_repository=FakeConnectionRepository(
                SimpleNamespace(id=10, database_type="postgresql", database_name="app_db")
            ),
            metadata_repository=FakeMetadataRepository(
                SimpleNamespace(
                    status="completed",
                    metadata_json={
                        "database_type": "postgresql",
                        "database_name": "app_db",
                        "schemas": [],
                        "relationships": [],
                    },
                )
            ),
            session_repository=FakeSessionRepository(SimpleNamespace(id=5, workspace_id=1)),
            workspace_repository=FakeWorkspaceRepository(SimpleNamespace(id=1)),
            message_repository=FakeMessageRepository(),
            prompt_record_repository=FakePromptRecordRepository(),
            query_record_repository=FakeQueryRecordRepository(),
            token_usage_repository=FakeTokenUsageRepository(),
            prompt_builder=prompt_builder,
            llm_client=llm_client,
            sql_validator=validator,
            query_executor=executor,
        )

        result = service.run_query("workspace-key", "session-key", "List users")

        self.assertEqual(result.row_count, 1)
        self.assertEqual(
            result.summary,
            "Fetches user IDs with a result cap for safe browsing.",
        )
        self.assertEqual(result.token_usage.total_tokens, 120)
        self.assertEqual(result.token_usage.cached_input_tokens, 12)
        self.assertEqual(llm_client.calls[0]["question"], "List users")
        self.assertEqual(validator.inputs, ["SELECT id FROM users LIMIT 10"])
        self.assertEqual(executor.inputs, ["SELECT id FROM users LIMIT 10"])
        self.assertEqual(service.message_repository.created[0].role, "user")
        self.assertEqual(service.message_repository.created[0].content, "List users")
        self.assertEqual(service.message_repository.created[1].role, "assistant")
        self.assertEqual(
            service.prompt_record_repository.created[0].assistant_message_id,
            service.message_repository.created[1].id,
        )
        self.assertIn("Database metadata:", service.prompt_record_repository.created[0].user_prompt)
        self.assertEqual(
            service.query_record_repository.created[0].assistant_message_id,
            service.message_repository.created[1].id,
        )
        self.assertEqual(
            service.token_usage_repository.created[0].message_id,
            service.message_repository.created[1].id,
        )
        self.assertEqual(service.token_usage_repository.created[0].provider, "groq")

    def test_run_query_requires_connection(self):
        service = self._build_service(connection=None)

        with self.assertRaises(DatabaseConnectionNotFound):
            service.run_query("workspace-key", "session-key", "List users")

    def test_run_query_requires_completed_metadata(self):
        service = self._build_service(metadata=SimpleNamespace(status="pending", metadata_json=None))

        with self.assertRaises(DatabaseMetadataNotReady):
            service.run_query("workspace-key", "session-key", "List users")

    def _build_service(self, connection="sentinel", metadata="sentinel"):
        if connection == "sentinel":
            connection = SimpleNamespace(id=10, database_type="postgresql", database_name="app_db")
        if metadata == "sentinel":
            metadata = SimpleNamespace(
                status="completed",
                metadata_json={
                    "database_type": "postgresql",
                    "database_name": "app_db",
                    "schemas": [],
                    "relationships": [],
                },
            )

        return QueryService(
            db=FakeDB(),
            connection_repository=FakeConnectionRepository(connection),
            metadata_repository=FakeMetadataRepository(metadata),
            session_repository=FakeSessionRepository(SimpleNamespace(id=5, workspace_id=1)),
            workspace_repository=FakeWorkspaceRepository(SimpleNamespace(id=1)),
            message_repository=FakeMessageRepository(),
            prompt_record_repository=FakePromptRecordRepository(),
            query_record_repository=FakeQueryRecordRepository(),
            token_usage_repository=FakeTokenUsageRepository(),
            prompt_builder=QueryPromptBuilder(),
            llm_client=FakeLLMClient("SELECT 1"),
            sql_validator=FakeValidator("SELECT 1"),
            query_executor=FakeExecutor(
                QueryResponse(
                    sql_query="SELECT 1",
                    summary="",
                    columns=["?column?"],
                    rows=[{"?column?": 1}],
                    row_count=1,
                    execution_time_ms=1,
                    truncated=False,
                    token_usage=QueryTokenUsage(
                        total_tokens=0,
                        input_tokens=0,
                        output_tokens=0,
                        cached_input_tokens=0,
                    ),
                )
            ),
        )


class FakeLLMClient:
    def __init__(self, sql_query, summary="Summary", token_usage=None):
        self.sql_query = sql_query
        self.summary = summary
        self.token_usage = token_usage or QueryTokenUsage(
            total_tokens=0,
            input_tokens=0,
            output_tokens=0,
            cached_input_tokens=0,
        )
        self.calls = []

    def generate_sql(self, system_prompt, user_prompt):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "question": self._extract_question(user_prompt),
            }
        )
        return SimpleNamespace(
            sql_query=self.sql_query,
            summary=self.summary,
            token_usage=self.token_usage,
            provider="groq",
            model_name="llama-3.3-70b-versatile",
        )

    def _extract_question(self, user_prompt):
        marker = "User question:\n"
        if marker not in user_prompt:
            return ""
        return user_prompt.split(marker, 1)[1].split("\n\n", 1)[0]


class FakeValidator:
    def __init__(self, result):
        self.result = result
        self.inputs = []

    def validate(self, sql_text):
        self.inputs.append(sql_text)
        return self.result


class FakeExecutor:
    def __init__(self, result):
        self.result = result
        self.inputs = []

    def execute(self, connection, sql_text):
        self.inputs.append(sql_text)
        return self.result


class FakeWorkspaceRepository:
    def __init__(self, workspace):
        self.workspace = workspace

    def get_by_key(self, workspace_key):
        return self.workspace


class FakeSessionRepository:
    def __init__(self, session):
        self.session = session

    def get_by_key(self, session_key, workspace_id):
        return self.session


class FakeConnectionRepository:
    def __init__(self, connection):
        self.connection = connection

    def get_successful_connection(self, session_id):
        return self.connection


class FakeMetadataRepository:
    def __init__(self, metadata):
        self.metadata = metadata

    def get_by_connection_id(self, connection_id):
        return self.metadata


class FakeMessageRepository:
    def __init__(self):
        self.created = []
        self._next_id = 1

    def create(self, message):
        if getattr(message, "id", None) is None:
            message.id = self._next_id
            self._next_id += 1
        self.created.append(message)
        return message


class FakeQueryRecordRepository:
    def __init__(self):
        self.created = []

    def create(self, query_record):
        self.created.append(query_record)
        return query_record


class FakePromptRecordRepository:
    def __init__(self):
        self.created = []

    def create(self, prompt_record):
        self.created.append(prompt_record)
        return prompt_record


class FakeTokenUsageRepository:
    def __init__(self):
        self.created = []

    def create(self, token_usage):
        self.created.append(token_usage)
        return token_usage


class FakeTransaction:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeDB:
    def __init__(self):
        self.commits = 0

    def begin(self):
        return FakeTransaction()

    def commit(self):
        self.commits += 1


class FakeConnectionRuntime:
    def __init__(self, engine):
        self.engine = engine

    def create_engine_for_connection(self, connection):
        return self.engine


class FakeRow:
    def __init__(self, mapping):
        self._mapping = mapping


class FakeResult:
    def __init__(self, rows, keys):
        self._rows = rows
        self._keys = keys

    def keys(self):
        return self._keys

    def fetchmany(self, size):
        return self._rows[:size]


class FakeDBConnection:
    def __init__(self, rows, keys):
        self.rows = rows
        self.keys_list = keys
        self.commands = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        self.commands.append((str(statement), params))
        if str(statement).startswith("SET "):
            return SimpleNamespace()
        return FakeResult(self.rows, self.keys_list)


class FailingDBConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        raise SQLAlchemyError("boom")


class FakeEngine:
    def __init__(self, connection):
        self.connection = connection
        self.disposed = False

    def connect(self):
        return self.connection

    def dispose(self):
        self.disposed = True
