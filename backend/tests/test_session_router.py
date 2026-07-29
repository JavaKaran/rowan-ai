import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.routers.session import get_session_service
from app.schemas import SessionResponse


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
            },
        )


class FakeSessionService:
    def get_session_by_key(self, workspace_key, session_key):
        return SessionResponse(session_key=session_key, name="Test session")
