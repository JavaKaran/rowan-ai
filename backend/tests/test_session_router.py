import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routers.session import get_session_service
from app.schemas import QueryTokenUsage, SessionQueryHistoryItem


class SessionRouterTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides[get_session_service] = lambda: FakeSessionService()

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_get_session_openapi_marks_workspace_header_optional(self):
        response = self.client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        parameters = response.json()["paths"]["/session/{session_key}"]["get"]["parameters"]

        workspace_header = next(
            parameter for parameter in parameters if parameter["name"] == "X-Workspace-Key"
        )

        self.assertFalse(workspace_header["required"])
        self.assertEqual(workspace_header["in"], "header")

    def test_get_session_allows_missing_workspace_header(self):
        response = self.client.get("/session/session-key")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "session_key": "session-key",
                "name": "Test session",
                "messages": [],
            },
        )

    def test_get_session_includes_message_history_in_query_response_schema(self):
        app.dependency_overrides[get_session_service] = lambda: FakeSessionService(
            history=[
                SessionQueryHistoryItem(
                    question="List users",
                    status="completed",
                    error_message=None,
                    sql_query="SELECT id FROM users LIMIT 10",
                    summary="Fetches user IDs.",
                    columns=["id"],
                    rows=[{"id": 1}],
                    row_count=1,
                    execution_time_ms=12,
                    truncated=False,
                    token_usage=QueryTokenUsage(
                        total_tokens=10, input_tokens=8, output_tokens=2, cached_input_tokens=0
                    ),
                    attempt_count=1,
                    repaired=False,
                    tool_calls=[],
                )
            ]
        )

        response = self.client.get("/session/session-key")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["messages"]), 1)
        self.assertEqual(body["messages"][0]["question"], "List users")
        self.assertEqual(body["messages"][0]["sql_query"], "SELECT id FROM users LIMIT 10")
        self.assertEqual(body["messages"][0]["status"], "completed")


class FakeSessionService:
    def __init__(self, history=None):
        self.history = history if history is not None else []

    def get_session_by_key(self, workspace_key, session_key):
        return SimpleNamespace(id=1, session_key=session_key, name="Test session")

    def get_session_history(self, session_id):
        return self.history
