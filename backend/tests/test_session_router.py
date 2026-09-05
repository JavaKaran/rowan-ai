import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.routers.session import get_session_service
from app.schemas import (
    QueryTokenUsage,
    SessionListResponse,
    SessionMetadata,
    SessionQueryHistoryItem,
    SessionResponse,
)


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
                "is_connected": False,
                "metadata": {
                    "database_name": None,
                    "database_type": None,
                    "is_connected": False,
                },
                "messages": [],
            },
        )

    def test_get_session_includes_is_connected(self):
        app.dependency_overrides[get_session_service] = lambda: FakeSessionService(
            is_connected=True
        )

        response = self.client.get("/session/session-key")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_connected"])

    def test_get_session_includes_metadata_with_data_info(self):
        app.dependency_overrides[get_session_service] = lambda: FakeSessionService(
            metadata=SessionMetadata(
                database_name="analytics",
                database_type="postgresql",
                is_connected=True,
            )
        )

        response = self.client.get("/session/session-key")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["metadata"],
            {
                "database_name": "analytics",
                "database_type": "postgresql",
                "is_connected": True,
            },
        )
        self.assertTrue(body["is_connected"])

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


    def test_list_sessions_requires_workspace_header(self):
        response = self.client.get("/session/")

        self.assertEqual(response.status_code, 400)

    def test_list_sessions_returns_paginated_items(self):
        app.dependency_overrides[get_session_service] = lambda: FakeSessionService(
            list_response=SessionListResponse(
                items=[
                    {
                        "session_key": "sess_1",
                        "name": "Chat 1",
                        "first_message": "How many users signed up last week?",
                        "is_connected": True,
                    }
                ],
                page=1,
                page_size=20,
                total=1,
                total_pages=1,
            )
        )

        response = self.client.get(
            "/session/", headers={"X-Workspace-Key": "workspace-key"}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["items"],
            [
                {
                    "session_key": "sess_1",
                    "name": "Chat 1",
                    "first_message": "How many users signed up last week?",
                    "is_connected": True,
                }
            ],
        )
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 20)
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["total_pages"], 1)

    def test_list_sessions_passes_page_query_param(self):
        service = FakeSessionService(
            list_response=SessionListResponse(
                items=[], page=3, page_size=20, total=45, total_pages=3
            )
        )
        app.dependency_overrides[get_session_service] = lambda: service

        response = self.client.get(
            "/session/?page=3", headers={"X-Workspace-Key": "workspace-key"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(service.list_calls, [("workspace-key", 3)])

    def test_list_sessions_rejects_page_below_one(self):
        response = self.client.get(
            "/session/?page=0", headers={"X-Workspace-Key": "workspace-key"}
        )

        self.assertEqual(response.status_code, 422)


class FakeSessionService:
    def __init__(self, history=None, list_response=None, is_connected=False, metadata=None):
        self.history = history if history is not None else []
        self.list_response = list_response
        self.is_connected = is_connected
        self.metadata = metadata
        self.list_calls = []
        self.detail_calls = []

    def get_session_detail(self, workspace_key, session_key):
        self.detail_calls.append((workspace_key, session_key))
        metadata = self.metadata
        if metadata is None:
            metadata = SessionMetadata(is_connected=self.is_connected)
        return SessionResponse(
            session_key=session_key,
            name="Test session",
            is_connected=metadata.is_connected,
            metadata=metadata,
            messages=self.history,
        )

    def list_sessions(self, workspace_key, page=1):
        self.list_calls.append((workspace_key, page))
        return self.list_response
