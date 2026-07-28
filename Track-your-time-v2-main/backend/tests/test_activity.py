"""
Focused backend tests for the reminder activity feature.
Coverage:
  1. Intent extraction — unit tests for all five intents and edge cases.
  2. Activity persistence — POST /activities/submit saves correct DB row.
  3. Source tracking — voice vs text source is stored correctly.
Run with:
  pytest tests/test_activity.py -v
"""
import os
import pytest
from app.services.intent_service import extract_intent
# ===========================================================================
# 1. Intent Extraction Unit Tests
# ===========================================================================
class TestExtractIntent:
    """Pure unit tests — no DB, no HTTP."""
    # --- completed ---
    def test_completed_basic(self):
        result = extract_intent("I completed login")
        assert result.activity_type == "completed"
        assert "login" in result.task_title.lower()
    def test_completed_finished(self):
        result = extract_intent("Finished backend")
        assert result.activity_type == "completed"
        assert "backend" in result.task_title.lower()
    def test_completed_done(self):
        result = extract_intent("Done with the frontend integration")
        assert result.activity_type == "completed"
    def test_completed_wrapped_up(self):
        result = extract_intent("Wrapped up authentication module")
        assert result.activity_type == "completed"
        assert "authentication" in result.task_title.lower()
    # --- started ---
    def test_started_basic(self):
        result = extract_intent("Started frontend")
        assert result.activity_type == "started"
        assert "frontend" in result.task_title.lower()
    def test_started_began(self):
        result = extract_intent("I began the database migration")
        assert result.activity_type == "started"
    def test_started_kicked_off(self):
        result = extract_intent("Kicked off the CI pipeline")
        assert result.activity_type == "started"
    # --- working ---
    def test_working_basic(self):
        result = extract_intent("I'm working on authentication")
        assert result.activity_type == "working"
        assert "authentication" in result.task_title.lower()
    def test_working_debugging(self):
        result = extract_intent("I'm debugging notifications")
        assert result.activity_type == "working"
        assert "notifications" in result.task_title.lower()
    def test_working_implementing(self):
        result = extract_intent("Implementing the new API endpoints")
        assert result.activity_type == "working"
    def test_working_currently(self):
        result = extract_intent("Currently reviewing pull requests")
        assert result.activity_type == "working"
    # --- blocked ---
    def test_blocked_basic(self):
        result = extract_intent("I'm blocked because Docker won't start")
        assert result.activity_type == "blocked"
        assert result.optional_notes is not None
        assert "docker" in result.optional_notes.lower()
    def test_blocked_stuck(self):
        result = extract_intent("Stuck on the database migration")
        assert result.activity_type == "blocked"
    def test_blocked_cant(self):
        result = extract_intent("Can't push to the repo because of auth issues")
        assert result.activity_type == "blocked"
        assert result.optional_notes is not None
    def test_blocked_error(self):
        result = extract_intent("Getting an error in the pipeline")
        assert result.activity_type == "blocked"
    def test_blocked_notes_split(self):
        result = extract_intent("Blocked on payments since the API key expired")
        assert result.activity_type == "blocked"
        assert result.optional_notes is not None
        assert "api key" in result.optional_notes.lower()
    # --- status_update (fallback) ---
    def test_status_update_fallback(self):
        result = extract_intent("Checking some things out")
        assert result.activity_type == "status_update"
    def test_status_update_empty_ish(self):
        result = extract_intent("General update for today")
        assert result.activity_type == "status_update"
        assert result.task_title  # title must not be empty
    # --- edge cases ---
    def test_title_never_empty(self):
        """task_title should always be a non-empty string."""
        inputs = [
            "done",
            "started",
            "working",
            "blocked",
            "I'm working on it",
        ]
        for text in inputs:
            result = extract_intent(text)
            assert result.task_title, f"Empty title for input: {text!r}"
    def test_case_insensitive(self):
        assert extract_intent("COMPLETED THE TASK").activity_type == "completed"
        assert extract_intent("STARTED THE BUILD").activity_type == "started"
    def test_real_example_inputs(self):
        """Validate the exact examples from the feature spec."""
        cases = [
            ("I'm working on authentication.", "working"),
            ("I completed login.", "completed"),
            ("I'm debugging notifications.", "working"),
            ("Started frontend.", "started"),
            ("Finished backend.", "completed"),
            ("I'm blocked because Docker won't start.", "blocked"),
        ]
        for text, expected_type in cases:
            result = extract_intent(text)
            assert result.activity_type == expected_type, (
                f"Input: {text!r}\n"
                f"Expected: {expected_type}\n"
                f"Got:      {result.activity_type}"
            )
# ===========================================================================
# 2. Integration Tests — Persistence + Endpoint
#    These require a running FastAPI app + test DB.
#    Run with: pytest tests/test_activity.py -v -m integration
# ===========================================================================
# Only attempt integration tests when the test suite has DB access.
# Importing here inside the mark block keeps the file importable without DB.
try:
    from httpx import AsyncClient, ASGITransport
    import asyncio
    from datetime import timezone, datetime
    _INTEGRATION_AVAILABLE = True
except ImportError:
    _INTEGRATION_AVAILABLE = False
@pytest.mark.skipif(
    not _INTEGRATION_AVAILABLE or os.getenv("RUN_ACTIVITY_INTEGRATION_TESTS") != "1",
    reason="activity integration test fixtures are not configured",
)
@pytest.mark.asyncio
class TestActivityEndpoint:
    """
    Integration tests for POST /activities/submit.
    Requires:
      - A running test database (or SQLite for unit integration).
      - A valid JWT token (fixture-provided).
    These tests are marked `integration` so they can be excluded in CI
    without a running Postgres instance:
        pytest tests/test_activity.py -v -k "not integration"
    """
    @pytest.mark.integration
    async def test_text_submission_persists(self, async_client: "AsyncClient", auth_headers: dict):
        """POST with source=text should return 201 and a persisted activity."""
        response = await async_client.post(
            "/activities/submit",
            json={"text": "I completed the login feature", "source": "text"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["activity_type"] == "completed"
        assert data["source"] == "text"
        assert data["task_title"]
        assert "id" in data
        assert "timestamp" in data
    @pytest.mark.integration
    async def test_voice_submission_persists(self, async_client: "AsyncClient", auth_headers: dict):
        """POST with source=voice should record source correctly."""
        response = await async_client.post(
            "/activities/submit",
            json={"text": "Started frontend development", "source": "voice"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["activity_type"] == "started"
        assert data["source"] == "voice"
    @pytest.mark.integration
    async def test_blocked_with_notes(self, async_client: "AsyncClient", auth_headers: dict):
        """Blocked intent should populate optional_notes."""
        response = await async_client.post(
            "/activities/submit",
            json={
                "text": "I'm blocked because Docker won't start",
                "source": "text",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["activity_type"] == "blocked"
        assert data["optional_notes"] is not None
    @pytest.mark.integration
    async def test_unauthorized_rejected(self, async_client: "AsyncClient"):
        """Requests without a valid token must be rejected."""
        response = await async_client.post(
            "/activities/submit",
            json={"text": "Finished backend", "source": "text"},
        )
        assert response.status_code == 401
    @pytest.mark.integration
    async def test_empty_text_rejected(self, async_client: "AsyncClient", auth_headers: dict):
        """Empty text must be rejected by Pydantic validation."""
        response = await async_client.post(
            "/activities/submit",
            json={"text": "", "source": "text"},
            headers=auth_headers,
        )
        assert response.status_code == 422
    @pytest.mark.integration
    async def test_invalid_source_rejected(self, async_client: "AsyncClient", auth_headers: dict):
        """Unknown source values must be rejected."""
        response = await async_client.post(
            "/activities/submit",
            json={"text": "Some update", "source": "telepathy"},
            headers=auth_headers,
        )
        assert response.status_code == 422
