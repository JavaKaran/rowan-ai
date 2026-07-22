import os
import unittest
from types import SimpleNamespace

from cryptography.fernet import Fernet
from fastapi import BackgroundTasks

from app.exceptions import DatabaseConnectionAlreadyExists
from app.schemas import DatabaseConnectionCreate
from app.services.database_connection import DatabaseConnectionService
from app.core.database_connections import encrypt_password
from app.services.database_metadata import DatabaseMetadataService
from app.services.metadata_jobs import FastAPIMetadataJobDispatcher


class FakeInspector:
    def get_columns(self, table_name, schema=None):
        columns = {
            "users": [
                {"name": "id", "type": "INTEGER", "nullable": False, "default": None},
            ],
            "orders": [
                {"name": "id", "type": "INTEGER", "nullable": False, "default": None},
                {
                    "name": "user_id",
                    "type": "INTEGER",
                    "nullable": False,
                    "default": None,
                },
            ],
        }
        return columns[table_name]

    def get_pk_constraint(self, table_name, schema=None):
        return {"constrained_columns": ["id"]}

    def get_foreign_keys(self, table_name, schema=None):
        if table_name == "orders":
            return [
                {
                    "constrained_columns": ["user_id"],
                    "referred_schema": schema,
                    "referred_table": "users",
                    "referred_columns": ["id"],
                }
            ]

        return []


class FakeMetadataRepository:
    def __init__(self):
        self.status_updates = []

    def update_status(
        self,
        metadata,
        status,
        progress_current=None,
        progress_total=None,
        metadata_json=None,
        error_message=None,
    ):
        self.status_updates.append(
            {
                "status": status,
                "progress_current": progress_current,
                "progress_total": progress_total,
            }
        )
        return metadata


class DatabaseMetadataServiceTest(unittest.TestCase):
    def test_build_metadata_json_includes_primary_keys_foreign_keys_and_relationships(self):
        metadata_repository = FakeMetadataRepository()
        service = DatabaseMetadataService(
            db=SimpleNamespace(),
            connection_repository=SimpleNamespace(),
            metadata_repository=metadata_repository,
        )

        metadata_json = service._build_metadata_json(
            connection=SimpleNamespace(
                database_type="postgresql",
                database_name="app_db",
            ),
            inspector=FakeInspector(),
            schemas=["public"],
            table_refs=[("public", "users"), ("public", "orders")],
            metadata=SimpleNamespace(),
        )

        users_table = metadata_json["schemas"][0]["tables"][0]
        orders_table = metadata_json["schemas"][0]["tables"][1]

        self.assertEqual(users_table["primary_key"], ["id"])
        self.assertEqual(orders_table["foreign_keys"][0]["columns"], ["user_id"])
        self.assertEqual(
            metadata_json["relationships"],
            [
                {
                    "from_schema": "public",
                    "from_table": "orders",
                    "from_columns": ["user_id"],
                    "to_schema": "public",
                    "to_table": "users",
                    "to_columns": ["id"],
                }
            ],
        )
        self.assertEqual(
            metadata_repository.status_updates[-1],
            {
                "status": "parsing_tables",
                "progress_current": 2,
                "progress_total": 2,
            },
        )


class FastAPIMetadataJobDispatcherTest(unittest.TestCase):
    def test_enqueue_parse_metadata_adds_background_task(self):
        background_tasks = BackgroundTasks()
        dispatcher = FastAPIMetadataJobDispatcher(background_tasks)

        dispatcher.enqueue_parse_metadata(123)

        self.assertEqual(len(background_tasks.tasks), 1)
        self.assertEqual(background_tasks.tasks[0].args, (123,))


class FakeConnectionRepository:
    def __init__(self, existing_connection):
        self.existing_connection = existing_connection
        self.created_connections = []

    def get_successful_connection(self, session_id):
        return self.existing_connection

    def create(self, connection):
        self.created_connections.append(connection)
        return connection


class FakeConnectionMetadataRepository:
    def __init__(self, metadata=None):
        self.metadata = metadata
        self.created_for_connection_ids = []
        self.status_updates = []

    def get_by_connection_id(self, database_connection_id):
        return self.metadata

    def create_pending(self, database_connection_id):
        self.created_for_connection_ids.append(database_connection_id)
        return SimpleNamespace(status="pending")

    def update_status(self, metadata, status, **kwargs):
        metadata.status = status
        self.status_updates.append({"status": status, **kwargs})
        return metadata


class FakeDispatcher:
    def __init__(self):
        self.enqueued_connection_ids = []

    def enqueue_parse_metadata(self, database_connection_id):
        self.enqueued_connection_ids.append(database_connection_id)


class DatabaseConnectionServiceReconnectTest(unittest.TestCase):
    def setUp(self):
        self.original_key = os.environ.get("DATABASE_CONNECTION_ENCRYPTION_KEY")
        os.environ["DATABASE_CONNECTION_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

    def tearDown(self):
        if self.original_key is None:
            os.environ.pop("DATABASE_CONNECTION_ENCRYPTION_KEY", None)
        else:
            os.environ["DATABASE_CONNECTION_ENCRYPTION_KEY"] = self.original_key

    def test_reconnect_with_same_connection_returns_existing_connection_and_enqueues_parse(self):
        existing_connection = SimpleNamespace(
            id=123,
            database_type="postgresql",
            host="localhost",
            port=5432,
            database_name="app_db",
            username="app_user",
            encrypted_password=encrypt_password("secret"),
            ssl_mode="prefer",
        )
        connection_repository = FakeConnectionRepository(existing_connection)
        metadata_repository = FakeConnectionMetadataRepository(
            metadata=SimpleNamespace(status="completed")
        )
        dispatcher = FakeDispatcher()
        service = self._build_service(
            connection_repository,
            metadata_repository,
            dispatcher,
        )

        result = service.create_connection(
            "workspace-key",
            "session-key",
            self._payload(),
        )

        self.assertEqual(result, existing_connection)
        self.assertEqual(connection_repository.created_connections, [])
        self.assertEqual(dispatcher.enqueued_connection_ids, [123])
        self.assertEqual(
            metadata_repository.status_updates,
            [
                {
                    "status": "pending",
                    "progress_current": 0,
                    "progress_total": 0,
                    "error_message": None,
                }
            ],
        )

    def test_reconnect_with_different_connection_raises_conflict(self):
        existing_connection = SimpleNamespace(
            id=123,
            database_type="postgresql",
            host="localhost",
            port=5432,
            database_name="app_db",
            username="app_user",
            encrypted_password=encrypt_password("secret"),
            ssl_mode="prefer",
        )
        service = self._build_service(
            FakeConnectionRepository(existing_connection),
            FakeConnectionMetadataRepository(),
            FakeDispatcher(),
        )

        with self.assertRaises(DatabaseConnectionAlreadyExists):
            service.create_connection(
                "workspace-key",
                "session-key",
                self._payload(database_name="other_db"),
            )

    def test_reconnect_with_missing_metadata_enqueues_metadata_parse(self):
        existing_connection = SimpleNamespace(
            id=123,
            database_type="postgresql",
            host="localhost",
            port=5432,
            database_name="app_db",
            username="app_user",
            encrypted_password=encrypt_password("secret"),
            ssl_mode="prefer",
        )
        metadata_repository = FakeConnectionMetadataRepository()
        dispatcher = FakeDispatcher()
        service = self._build_service(
            FakeConnectionRepository(existing_connection),
            metadata_repository,
            dispatcher,
        )

        service.create_connection("workspace-key", "session-key", self._payload())

        self.assertEqual(metadata_repository.created_for_connection_ids, [123])
        self.assertEqual(dispatcher.enqueued_connection_ids, [123])

    def _build_service(
        self,
        connection_repository,
        metadata_repository,
        dispatcher,
    ):
        return DatabaseConnectionService(
            repository=connection_repository,
            metadata_repository=metadata_repository,
            metadata_job_dispatcher=dispatcher,
            session_repository=SimpleNamespace(
                get_by_key=lambda session_key, workspace_id: SimpleNamespace(id=456)
            ),
            workspace_repository=SimpleNamespace(
                get_by_key=lambda workspace_key: SimpleNamespace(id=789)
            ),
        )

    def _payload(self, database_name="app_db"):
        return DatabaseConnectionCreate(
            database_type="postgresql",
            host="localhost",
            port=5432,
            database_name=database_name,
            username="app_user",
            password="secret",
            ssl_mode="prefer",
        )


if __name__ == "__main__":
    unittest.main()
