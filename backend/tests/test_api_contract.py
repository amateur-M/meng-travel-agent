"""Frontend ↔ backend URL contract.

The frontend's service layer is stubbed by the store checks, and nothing in
this environment drives the app from a real browser. So a renamed path, a
changed method, or a misspelled query parameter would only be discovered at
runtime by clicking around.

This test reads the URLs the frontend actually calls out of
``frontend/src/services/chat.ts`` and checks them against the app's own
OpenAPI schema. It is deliberately shape-based: placeholder *names* are ignored
(``{session_id}`` vs ``${sessionId}``), because only their position in the path
matters.
"""

import re
from pathlib import Path

import pytest

from main import app

CHAT_SERVICE = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "services" / "chat.ts"
)

# api.get(`/api/...`) / api.post("/api/...") / ...
CALL_RE = re.compile(r"api\.(get|post|patch|delete)\(\s*[`\"]([^`\"]+)[`\"]")


def _shape(path: str) -> str:
    """Normalise placeholders so only their position is compared."""
    return re.sub(r"\{[^}]+\}", "{}", path.split("?")[0].rstrip("/"))


def _schema():
    return app.openapi()


def _frontend_calls() -> list[tuple[str, str]]:
    if not CHAT_SERVICE.exists():
        pytest.skip(f"frontend service not checked out: {CHAT_SERVICE}")
    source = CHAT_SERVICE.read_text(encoding="utf-8")
    calls = [
        (method.upper(), re.sub(r"\$\{[^}]+\}", "{}", url))
        for method, url in CALL_RE.findall(source)
    ]
    # A literal `${...}` inside a template string is a frontend placeholder.
    calls = [(m, re.sub(r"\{[^}]+\}", "{}", u)) for m, u in calls]
    assert calls, "no API calls found — did the frontend service move?"
    return calls


class TestFrontendBackendContract:

    def test_every_frontend_url_exists_in_the_schema(self):
        paths = {_shape(p): p for p in _schema()["paths"]}
        unknown = [
            (method, url)
            for method, url in _frontend_calls()
            if _shape(url) not in paths
        ]
        assert not unknown, f"frontend calls routes the backend does not define: {unknown}"

    def test_every_frontend_url_uses_a_supported_method(self):
        schema = _schema()["paths"]
        paths = {_shape(p): p for p in schema}
        mismatched = []
        for method, url in _frontend_calls():
            real = paths.get(_shape(url))
            if real is None:
                continue  # covered by the previous test
            if method.lower() not in schema[real]:
                mismatched.append((method, real, sorted(schema[real])))
        assert not mismatched, f"method mismatch: {mismatched}"

    def test_client_id_query_parameter_is_declared(self):
        """The frontend scopes sessions and profiles by client_id."""
        source = CHAT_SERVICE.read_text(encoding="utf-8")
        assert "client_id" in source, "the frontend stopped sending client_id"

        schema = _schema()["paths"]
        sessions_path = next(p for p in schema if _shape(p) == "/api/chat/sessions")
        declared = {
            param["name"]
            for param in schema[sessions_path]["get"].get("parameters", [])
        }
        assert "client_id" in declared, (
            "GET /api/chat/sessions no longer accepts client_id, so the sidebar "
            "would list every conversation"
        )

    def test_message_and_session_fields_the_frontend_sends_are_accepted(self):
        """Unknown body fields would be silently dropped by Pydantic."""
        schema = _schema()
        chat_body = schema["components"]["schemas"]["ChatRequest"]["properties"]
        for field in ("message", "session_id", "client_id", "message_id"):
            assert field in chat_body, f"ChatRequest lost '{field}'"

        plan_body = schema["components"]["schemas"]["TripPlanRequest"]["properties"]
        assert "session_id" in plan_body, (
            "TripPlanRequest lost session_id, so a finished trip could no longer "
            "be linked back to its conversation"
        )

    def test_response_fields_the_frontend_reads_are_present(self):
        """The store reads these off the wire; renaming them breaks hydration."""
        schemas = _schema()["components"]["schemas"]

        reply = schemas["ChatReply"]["properties"]
        for field in ("session_id", "reply", "intent", "slots", "ready", "plan_request"):
            assert field in reply, f"ChatReply lost '{field}'"

        message = schemas["ChatMessageItem"]["properties"]
        for field in ("role", "content", "message_id"):
            assert field in message, f"ChatMessageItem lost '{field}'"

        detail = schemas["SessionDetail"]["properties"]
        for field in ("session_id", "title", "slots", "plan_request", "last_plan_id"):
            assert field in detail, f"SessionDetail lost '{field}'"
