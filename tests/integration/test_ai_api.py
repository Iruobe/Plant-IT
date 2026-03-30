"""
Integration tests for AI API endpoints.

Tests the full request/response cycle for AI operations.
Uses mocked Bedrock service to avoid actual AI calls.

Endpoints tested:
- POST /api/v1/ai/scan (plant health scan)
- POST /api/v1/ai/chat (chat with assistant)
- POST /api/v1/ai/recommendations (plant recommendations)
- DELETE /api/v1/ai/chat/{session_id} (clear chat)
"""

import pytest
from unittest.mock import patch, MagicMock
import json


class TestScanPlant:
    """Tests for POST /api/v1/ai/scan"""

    @pytest.fixture
    def plant_with_image(
        self, authenticated_client, create_test_plant, mock_firebase_user
    ):
        """Create a plant with an image URL set."""
        plant = create_test_plant()
        plant_id = plant["plant_id"]
        user_id = mock_firebase_user["uid"]

        # Confirm upload to set image_url
        key = f"plants/{user_id}/{plant_id}/photo.jpg"
        authenticated_client.post(f"/api/v1/plants/{plant_id}/confirm-upload?key={key}")

        return plant

    def test_scan_plant_success(self, authenticated_client, plant_with_image):
        """Scanning a plant with image returns health analysis."""
        with patch("app.api.v1.ai.analyze_plant_image") as mock_analyze:
            mock_analyze.return_value = {
                "scan_id": "test_scan_123",
                "health_score": 85,
                "health_status": "healthy",
                "issues": ["Minor dust on leaves"],
                "recommendations": ["Wipe leaves monthly"],
                "summary": "Your plant is healthy.",
                "scanned_at": "2024-01-15T12:00:00",
            }

            response = authenticated_client.post(
                "/api/v1/ai/scan", json={"plant_id": plant_with_image["plant_id"]}
            )

        assert response.status_code == 200
        data = response.json()
        assert "health_score" in data
        assert "health_status" in data

    def test_scan_plant_not_found(self, authenticated_client, mock_bedrock):
        """Scanning a non-existent plant returns 404."""
        from uuid import uuid4

        response = authenticated_client.post(
            "/api/v1/ai/scan", json={"plant_id": str(uuid4())}
        )

        assert response.status_code == 404

    def test_scan_plant_no_image(
        self, authenticated_client, create_test_plant, mock_bedrock
    ):
        """Scanning a plant without image returns 400."""
        plant = create_test_plant()

        response = authenticated_client.post(
            "/api/v1/ai/scan", json={"plant_id": plant["plant_id"]}
        )

        assert response.status_code == 400
        assert "image" in response.json()["detail"].lower()

    def test_scan_plant_invalid_uuid(self, authenticated_client, mock_bedrock):
        """Scanning with invalid plant_id format returns 400/422."""
        response = authenticated_client.post(
            "/api/v1/ai/scan", json={"plant_id": "not-a-valid-uuid"}
        )

        assert response.status_code in [400, 422]

    def test_scan_plant_unauthorized(self, client):
        """Scanning without auth returns 401."""
        from uuid import uuid4

        response = client.post("/api/v1/ai/scan", json={"plant_id": str(uuid4())})

        assert response.status_code == 401


class TestChat:
    """Tests for POST /api/v1/ai/chat"""

    @pytest.fixture
    def mock_chat_service(self):
        """Mock the chat service."""
        with patch("app.api.v1.ai.chat_with_assistant") as mock:
            mock.return_value = {
                "response": "Water your monstera when the top inch of soil is dry.",
                "session_id": "test_session",
            }
            yield mock

    def test_chat_success(self, authenticated_client, mock_chat_service):
        """Sending a chat message returns AI response."""
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "How do I care for my monstera?",
                "session_id": "test_session",
            },
        )

        assert response.status_code == 200

        data = response.json()
        assert "response" in data
        assert "session_id" in data
        assert len(data["response"]) > 0

    def test_chat_with_plant_context(
        self, authenticated_client, create_test_plant, mock_chat_service
    ):
        """Sending a chat with plant_id includes plant context."""
        plant = create_test_plant()

        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "What's wrong with this plant?",
                "session_id": "test_session",
                "plant_id": plant["plant_id"],
            },
        )

        assert response.status_code == 200

    def test_chat_empty_message_fails(self, authenticated_client, mock_chat_service):
        """Sending empty message returns 400/422."""
        response = authenticated_client.post(
            "/api/v1/ai/chat", json={"message": "", "session_id": "test_session"}
        )

        assert response.status_code in [400, 422]

    def test_chat_message_too_long_fails(self, authenticated_client, mock_chat_service):
        """Sending message > 2000 chars returns 400/422."""
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={"message": "A" * 2001, "session_id": "test_session"},
        )

        assert response.status_code in [400, 422]

    def test_chat_invalid_session_id_fails(
        self, authenticated_client, mock_chat_service
    ):
        """Sending invalid session_id returns 400/422."""
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={"message": "Hello", "session_id": "invalid/session@id"},
        )

        assert response.status_code in [400, 422]

    def test_chat_unauthorized(self, client):
        """Chatting without auth returns 401."""
        response = client.post("/api/v1/ai/chat", json={"message": "Hello"})

        assert response.status_code == 401


class TestClearChat:
    """Tests for DELETE /api/v1/ai/chat/{session_id}"""

    @pytest.fixture
    def mock_clear_chat(self):
        """Mock the clear chat service."""
        with patch("app.api.v1.ai.clear_chat_session") as mock:
            mock.return_value = {"message": "Chat cleared"}
            yield mock

    def test_clear_chat_success(self, authenticated_client, mock_clear_chat):
        """Clearing chat returns success."""
        response = authenticated_client.delete("/api/v1/ai/chat/test_session")

        assert response.status_code == 200

    def test_clear_chat_unauthorized(self, client):
        """Clearing chat without auth returns 401."""
        response = client.delete("/api/v1/ai/chat/test_session")

        assert response.status_code == 401


class TestRecommendations:
    """Tests for POST /api/v1/ai/recommendations"""

    @pytest.fixture
    def mock_recommendations_service(self):
        """Mock the recommendations service."""
        with patch("app.api.v1.ai.get_plant_recommendations") as mock:
            mock.return_value = {
                "climate_summary": "Temperate climate",
                "recommendations": [
                    {
                        "common_name": "Snake Plant",
                        "scientific_name": "Sansevieria trifasciata",
                        "match_reason": "Low maintenance, perfect for beginners",
                        "difficulty": "easy",
                        "care_tips": ["Water monthly", "Indirect light"],
                    }
                ],
                "general_advice": "Start with low-maintenance plants.",
            }
            yield mock

    def test_recommendations_success(
        self, authenticated_client, mock_recommendations_service
    ):
        """Getting recommendations returns plant suggestions."""
        response = authenticated_client.post(
            "/api/v1/ai/recommendations",
            json={
                "goals": ["decorative", "air_purifying"],
                "experience_level": "beginner",
            },
        )

        assert response.status_code == 200

        data = response.json()
        assert "recommendations" in data
        assert len(data["recommendations"]) > 0

    def test_recommendations_with_location(
        self, authenticated_client, mock_recommendations_service
    ):
        """Getting recommendations with location works."""
        response = authenticated_client.post(
            "/api/v1/ai/recommendations",
            json={
                "goals": ["food"],
                "latitude": 51.5074,
                "longitude": -0.1278,
                "experience_level": "intermediate",
            },
        )

        assert response.status_code == 200

    def test_recommendations_unauthorized(self, client):
        """Getting recommendations without auth returns 401."""
        response = client.post(
            "/api/v1/ai/recommendations", json={"goals": ["decorative"]}
        )

        assert response.status_code == 401
