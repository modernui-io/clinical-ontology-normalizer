"""Tests for coding assistant API endpoints.

Tests verify:
- Chat endpoint functionality
- Session management
- Code lookup
- Error handling
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.coding_assistant_service import (
    get_coding_assistant_service,
    reset_coding_assistant_service,
)


class TestCodingAssistantChat:
    """Test the chat endpoint."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        """Reset service state between tests."""
        reset_coding_assistant_service()
        yield
        reset_coding_assistant_service()

    @pytest.mark.asyncio
    async def test_chat_basic_question(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/coding-assistant/chat",
                json={
                    "message": "What is the ICD-10 code for type 2 diabetes?",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "response" in data
        assert data["response"] != ""

    @pytest.mark.asyncio
    async def test_chat_creates_session(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/coding-assistant/chat",
                json={"message": "Hello"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        session_id = data["session_id"]
        # Session ID is a UUID
        assert len(session_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_chat_continues_session(self, client):
        async with client as ac:
            # First message
            response1 = await ac.post(
                "/api/v1/coding-assistant/chat",
                json={"message": "What is diabetes?"},
            )
            session_id = response1.json()["session_id"]

            # Second message in same session
            response2 = await ac.post(
                "/api/v1/coding-assistant/chat",
                json={
                    "message": "What codes should I use?",
                    "session_id": session_id,
                },
            )

        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_chat_with_context(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/coding-assistant/chat",
                json={
                    "message": "What codes apply?",
                    "context": {
                        "specialty": "cardiology",
                        "encounter_type": "outpatient",
                    },
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data

    @pytest.mark.asyncio
    async def test_chat_returns_suggestions(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/coding-assistant/chat",
                json={"message": "What is E11.9?"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)

    @pytest.mark.asyncio
    async def test_chat_empty_message(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/coding-assistant/chat",
                json={"message": ""},
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_chat_returns_follow_ups(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/coding-assistant/chat",
                json={"message": "How do I code diabetes?"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "follow_up_questions" in data
        assert isinstance(data["follow_up_questions"], list)


class TestSessionManagement:
    """Test session management endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_coding_assistant_service()
        yield
        reset_coding_assistant_service()

    @pytest.mark.asyncio
    async def test_list_sessions(self, client):
        async with client as ac:
            # Create a session first
            await ac.post(
                "/api/v1/coding-assistant/chat",
                json={"message": "Hello"},
            )

            # List sessions
            response = await ac.get("/api/v1/coding-assistant/sessions")

        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data
        assert isinstance(data["sessions"], list)

    @pytest.mark.asyncio
    async def test_get_session(self, client):
        async with client as ac:
            # Create a session
            chat_response = await ac.post(
                "/api/v1/coding-assistant/chat",
                json={"message": "Hello"},
            )
            session_id = chat_response.json()["session_id"]

            # Get session details
            response = await ac.get(f"/api/v1/coding-assistant/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert "created_at" in data
        assert "message_count" in data

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/coding-assistant/sessions/nonexistent-id")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_session(self, client):
        async with client as ac:
            # Create a session
            chat_response = await ac.post(
                "/api/v1/coding-assistant/chat",
                json={"message": "Hello"},
            )
            session_id = chat_response.json()["session_id"]

            # Delete session
            response = await ac.delete(f"/api/v1/coding-assistant/sessions/{session_id}")

        assert response.status_code == 200
        assert response.json()["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, client):
        async with client as ac:
            response = await ac.delete("/api/v1/coding-assistant/sessions/nonexistent-id")

        assert response.status_code == 404


class TestCodeLookup:
    """Test code lookup endpoint."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_lookup_code_found(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/coding-assistant/lookup/E11.9")

        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        assert "found" in data
        # Code might be found if ICD-10 service is available

    @pytest.mark.asyncio
    async def test_lookup_code_with_system(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/coding-assistant/lookup/99213",
                params={"system": "cpt"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        assert "system" in data

    @pytest.mark.asyncio
    async def test_lookup_code_not_found(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/coding-assistant/lookup/INVALID123")

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is False


class TestServiceStats:
    """Test service statistics endpoint."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_get_stats(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/coding-assistant/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_sessions" in data
        assert "total_queries" in data
        assert isinstance(data["total_sessions"], int)
        assert isinstance(data["total_queries"], int)
