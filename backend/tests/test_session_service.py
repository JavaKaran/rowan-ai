import unittest
from types import SimpleNamespace

from app.exceptions import WorkspaceNotFound
from app.services.session import SessionService


class SessionServiceHistoryTest(unittest.TestCase):
    def test_get_session_history_maps_query_records_into_query_response_schema(self):
        query_record = SimpleNamespace(
            status="completed",
            error_message=None,
            sql_query="SELECT id FROM users LIMIT 10",
            response_columns=["id"],
            response_rows=[{"id": 1}],
            row_count=1,
            execution_time_ms=12,
            truncated=False,
            attempts=[
                SimpleNamespace(
                    attempt_number=1,
                    tool_calls=[
                        {
                            "name": "find_relevant_tables",
                            "args": {"question": "List users"},
                            "result": [{"schema": "public", "table": "users"}],
                        }
                    ],
                )
            ],
            assistant_message=SimpleNamespace(
                content="Fetches user IDs.",
                prompt_record=SimpleNamespace(user_question="List users"),
                tokens=[
                    SimpleNamespace(
                        total_tokens=10,
                        input_tokens=8,
                        output_tokens=2,
                        cached_input_tokens=0,
                    )
                ],
            ),
        )
        repository = FakeQueryRecordRepository([query_record])
        service = SessionService(
            repository=None,
            workspace_repository=None,
            query_record_repository=repository,
        )

        history = service.get_session_history(session_id=5)

        self.assertEqual(repository.session_ids, [5])
        self.assertEqual(len(history), 1)
        item = history[0]
        self.assertEqual(item.question, "List users")
        self.assertEqual(item.status, "completed")
        self.assertIsNone(item.error_message)
        self.assertEqual(item.sql_query, "SELECT id FROM users LIMIT 10")
        self.assertEqual(item.summary, "Fetches user IDs.")
        self.assertEqual(item.token_usage.total_tokens, 10)
        self.assertEqual(item.attempt_count, 1)
        self.assertFalse(item.repaired)
        self.assertEqual(len(item.tool_calls), 1)
        self.assertEqual(item.tool_calls[0].name, "find_relevant_tables")
        self.assertEqual(item.tool_calls[0].attempt_number, 1)

    def test_get_session_history_marks_multi_attempt_success_as_repaired(self):
        query_record = SimpleNamespace(
            status="completed",
            error_message=None,
            sql_query="SELECT id FROM users LIMIT 10",
            response_columns=["id"],
            response_rows=[],
            row_count=0,
            execution_time_ms=1,
            truncated=False,
            attempts=[
                SimpleNamespace(attempt_number=1, tool_calls=[]),
                SimpleNamespace(attempt_number=2, tool_calls=[]),
            ],
            assistant_message=SimpleNamespace(
                content="",
                prompt_record=SimpleNamespace(user_question="List users"),
                tokens=[],
            ),
        )
        repository = FakeQueryRecordRepository([query_record])
        service = SessionService(
            repository=None,
            workspace_repository=None,
            query_record_repository=repository,
        )

        history = service.get_session_history(session_id=5)

        self.assertTrue(history[0].repaired)
        self.assertEqual(history[0].token_usage.total_tokens, 0)


class SessionServiceListTest(unittest.TestCase):
    def test_list_sessions_returns_paginated_items(self):
        sessions = [
            SimpleNamespace(id=i, session_key=f"sess_{i}", name=f"Chat {i}")
            for i in range(3)
        ]
        repository = FakeSessionRepository(sessions=sessions, total=45)
        workspace_repository = FakeWorkspaceRepository(SimpleNamespace(id=1))
        service = SessionService(
            repository=repository,
            workspace_repository=workspace_repository,
        )

        result = service.list_sessions("workspace-key", page=2)

        self.assertEqual(repository.calls, [(1, 2, 20)])
        self.assertEqual(len(result.items), 3)
        self.assertEqual(result.items[0].session_key, "sess_0")
        self.assertEqual(result.page, 2)
        self.assertEqual(result.page_size, 20)
        self.assertEqual(result.total, 45)
        self.assertEqual(result.total_pages, 3)

    def test_list_sessions_includes_first_user_message(self):
        sessions = [SimpleNamespace(id=0, session_key="sess_0", name=None)]
        repository = FakeSessionRepository(sessions=sessions, total=1)
        message_repository = FakeMessageRepository(
            {0: SimpleNamespace(content="How many users signed up last week?")}
        )
        service = SessionService(
            repository=repository,
            workspace_repository=FakeWorkspaceRepository(SimpleNamespace(id=1)),
            message_repository=message_repository,
        )

        result = service.list_sessions("workspace-key")

        self.assertEqual(
            result.items[0].first_message, "How many users signed up last week?"
        )

    def test_list_sessions_first_message_is_none_when_no_messages_yet(self):
        sessions = [SimpleNamespace(id=0, session_key="sess_0", name=None)]
        repository = FakeSessionRepository(sessions=sessions, total=1)
        service = SessionService(
            repository=repository,
            workspace_repository=FakeWorkspaceRepository(SimpleNamespace(id=1)),
            message_repository=FakeMessageRepository({}),
        )

        result = service.list_sessions("workspace-key")

        self.assertIsNone(result.items[0].first_message)

    def test_list_sessions_includes_is_connected(self):
        sessions = [
            SimpleNamespace(id=1, session_key="sess_connected", name=None),
            SimpleNamespace(id=2, session_key="sess_not_connected", name=None),
        ]
        repository = FakeSessionRepository(sessions=sessions, total=2)
        service = SessionService(
            repository=repository,
            workspace_repository=FakeWorkspaceRepository(SimpleNamespace(id=1)),
            database_connection_repository=FakeDatabaseConnectionRepository({1}),
        )

        result = service.list_sessions("workspace-key")

        self.assertTrue(result.items[0].is_connected)
        self.assertFalse(result.items[1].is_connected)

    def test_list_sessions_includes_metadata_matching_detail(self):
        sessions = [SimpleNamespace(id=1, session_key="sess_0", name=None)]
        repository = FakeSessionRepository(sessions=sessions, total=1)
        service = SessionService(
            repository=repository,
            workspace_repository=FakeWorkspaceRepository(SimpleNamespace(id=1)),
            query_record_repository=FakeQueryRecordRepository([]),
            database_connection_repository=FakeDatabaseConnectionRepository(
                {1},
                {
                    1: SimpleNamespace(
                        database_name="analytics",
                        database_type="mysql",
                    )
                },
            ),
        )

        result = service.list_sessions("workspace-key")
        detail = service.get_session_detail("workspace-key", "sess_0")

        self.assertEqual(result.items[0].metadata.database_name, "analytics")
        self.assertEqual(result.items[0].metadata.database_type, "mysql")
        self.assertTrue(result.items[0].metadata.is_connected)
        self.assertEqual(result.items[0].metadata, detail.metadata)

    def test_list_sessions_is_connected_defaults_false_without_repository(self):
        sessions = [SimpleNamespace(id=1, session_key="sess_0", name=None)]
        repository = FakeSessionRepository(sessions=sessions, total=1)
        service = SessionService(
            repository=repository,
            workspace_repository=FakeWorkspaceRepository(SimpleNamespace(id=1)),
        )

        result = service.list_sessions("workspace-key")

        self.assertFalse(result.items[0].is_connected)

    def test_list_sessions_defaults_to_page_one(self):
        repository = FakeSessionRepository(sessions=[], total=0)
        service = SessionService(
            repository=repository,
            workspace_repository=FakeWorkspaceRepository(SimpleNamespace(id=1)),
        )

        result = service.list_sessions("workspace-key")

        self.assertEqual(repository.calls, [(1, 1, 20)])
        self.assertEqual(result.total_pages, 0)
        self.assertEqual(result.items, [])

    def test_list_sessions_raises_workspace_not_found(self):
        service = SessionService(
            repository=FakeSessionRepository(sessions=[], total=0),
            workspace_repository=FakeWorkspaceRepository(None),
        )

        with self.assertRaises(WorkspaceNotFound):
            service.list_sessions("missing-workspace")


class SessionServiceIsConnectedTest(unittest.TestCase):
    def test_is_session_connected_true_when_repository_reports_connection(self):
        service = SessionService(
            repository=None,
            workspace_repository=None,
            database_connection_repository=FakeDatabaseConnectionRepository({5}),
        )

        self.assertTrue(service.is_session_connected(5))
        self.assertFalse(service.is_session_connected(6))

    def test_is_session_connected_false_without_repository(self):
        service = SessionService(repository=None, workspace_repository=None)

        self.assertFalse(service.is_session_connected(5))


class SessionServiceDetailTest(unittest.TestCase):
    def test_get_session_detail_includes_metadata_matching_listing(self):
        sessions = [SimpleNamespace(id=7, session_key="sess_7", name="Chat")]
        service = SessionService(
            repository=FakeSessionRepository(sessions=sessions, total=1),
            workspace_repository=FakeWorkspaceRepository(SimpleNamespace(id=1)),
            query_record_repository=FakeQueryRecordRepository([]),
            database_connection_repository=FakeDatabaseConnectionRepository(
                {7},
                {
                    7: SimpleNamespace(
                        database_name="analytics",
                        database_type="postgresql",
                    )
                },
            ),
        )

        detail = service.get_session_detail("workspace-key", "sess_7")
        listing = service.list_sessions("workspace-key")

        self.assertEqual(detail.session_key, "sess_7")
        self.assertEqual(detail.name, "Chat")
        self.assertEqual(detail.messages, [])
        self.assertTrue(detail.is_connected)
        self.assertEqual(
            detail.metadata.is_connected, listing.items[0].is_connected
        )
        self.assertEqual(detail.metadata.database_name, "analytics")
        self.assertEqual(detail.metadata.database_type, "postgresql")

    def test_get_session_detail_metadata_empty_without_connection(self):
        sessions = [SimpleNamespace(id=7, session_key="sess_7", name=None)]
        service = SessionService(
            repository=FakeSessionRepository(sessions=sessions, total=1),
            workspace_repository=FakeWorkspaceRepository(SimpleNamespace(id=1)),
            query_record_repository=FakeQueryRecordRepository([]),
            database_connection_repository=FakeDatabaseConnectionRepository(set()),
        )

        detail = service.get_session_detail("workspace-key", "sess_7")

        self.assertFalse(detail.is_connected)
        self.assertIsNone(detail.metadata.database_name)
        self.assertIsNone(detail.metadata.database_type)
        self.assertFalse(detail.metadata.is_connected)


class FakeDatabaseConnectionRepository:
    def __init__(self, connected_session_ids, connections_by_session_id=None):
        self.connected_session_ids = connected_session_ids
        self.connections_by_session_id = connections_by_session_id or {}

    def has_successful_connection(self, session_id):
        return session_id in self.connected_session_ids

    def get_successful_connection(self, session_id):
        if session_id not in self.connected_session_ids:
            return None
        return self.connections_by_session_id.get(
            session_id,
            SimpleNamespace(database_name="analytics", database_type="postgresql"),
        )


class FakeSessionRepository:
    def __init__(self, sessions, total):
        self.sessions = sessions
        self.total = total
        self.calls = []

    def get_by_key(self, session_key, workspace_id=None):
        return next(
            (s for s in self.sessions if s.session_key == session_key), None
        )

    def list_for_workspace(self, workspace_id, page, page_size):
        self.calls.append((workspace_id, page, page_size))
        return self.sessions, self.total


class FakeMessageRepository:
    def __init__(self, first_messages_by_session_id):
        self.first_messages_by_session_id = first_messages_by_session_id

    def get_first_user_query(self, session_id):
        return self.first_messages_by_session_id.get(session_id)


class FakeWorkspaceRepository:
    def __init__(self, workspace):
        self.workspace = workspace

    def get_by_key(self, workspace_key):
        return self.workspace


class FakeQueryRecordRepository:
    def __init__(self, query_records):
        self.query_records = query_records
        self.session_ids = []

    def list_for_session(self, session_id):
        self.session_ids.append(session_id)
        return self.query_records


if __name__ == "__main__":
    unittest.main()
