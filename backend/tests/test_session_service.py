import unittest
from types import SimpleNamespace

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


class FakeQueryRecordRepository:
    def __init__(self, query_records):
        self.query_records = query_records
        self.session_ids = []

    def list_for_session(self, session_id):
        self.session_ids.append(session_id)
        return self.query_records


if __name__ == "__main__":
    unittest.main()
