import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.routers.query import get_query_service
from app.schemas import QueryResponse, QueryTokenUsage


class QueryRouterTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides[get_query_service] = lambda: FakeQueryService()

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_query_endpoint_returns_structured_result(self):
        response = self.client.post(
            "/query/",
            headers={
                "X-Workspace-Key": "workspace-key",
                "X-Session-Key": "session-key",
            },
            json={"question": "List users"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "sql_query": "SELECT id FROM users LIMIT 1",
                "summary": "Returns one user ID from the users table.",
                "columns": ["id"],
                "rows": [{"id": 1}],
                "row_count": 1,
                "execution_time_ms": 7,
                "truncated": False,
                "token_usage": {
                    "total_tokens": 36,
                    "input_tokens": 24,
                    "output_tokens": 12,
                    "cached_input_tokens": 4,
                },
                "attempt_count": 1,
                "repaired": False,
                "tool_calls": [],
            },
        )

    def test_query_endpoint_requires_headers(self):
        response = self.client.post("/query/", json={"question": "List users"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "X-Workspace-Key header is required")


class FakeQueryService:
    def run_query(self, workspace_key, session_key, question):
        return QueryResponse(
            sql_query="SELECT id FROM users LIMIT 1",
            summary="Returns one user ID from the users table.",
            columns=["id"],
            rows=[{"id": 1}],
            row_count=1,
            execution_time_ms=7,
            truncated=False,
            token_usage=QueryTokenUsage(
                total_tokens=36,
                input_tokens=24,
                output_tokens=12,
                cached_input_tokens=4,
            ),
        )
