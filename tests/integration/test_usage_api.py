"""
Integration tests for Usage API endpoints.

Tests the usage tracking endpoints for rate limit monitoring.

Endpoints tested:
- GET /api/v1/usage/ (all endpoint usage)
- GET /api/v1/usage/{endpoint_key} (specific endpoint usage)
"""

import pytest


class TestGetUsage:
    """Tests for GET /api/v1/usage/"""
    
    def test_get_usage_success(self, authenticated_client):
        """Getting usage returns all endpoint stats."""
        response = authenticated_client.get("/api/v1/usage/")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "user_id" in data
        assert "usage" in data
        
        # Should include all rate-limited endpoints
        usage = data["usage"]
        assert "ai_scan" in usage
        assert "ai_chat" in usage
        assert "ai_recommendations" in usage
        assert "care_plans_generate" in usage
    
    def test_get_usage_shows_zero_for_new_user(self, authenticated_client):
        """New users should have 0 usage for all endpoints."""
        response = authenticated_client.get("/api/v1/usage/")
        
        assert response.status_code == 200
        
        usage = response.json()["usage"]
        for endpoint, stats in usage.items():
            assert stats["used"] == 0
    
    def test_get_usage_unauthorized(self, client):
        """Getting usage without auth returns 401."""
        response = client.get("/api/v1/usage/")
        
        assert response.status_code == 401


class TestGetEndpointUsage:
    """Tests for GET /api/v1/usage/{endpoint_key}"""
    
    def test_get_endpoint_usage_success(self, authenticated_client):
        """Getting specific endpoint usage returns its stats."""
        response = authenticated_client.get("/api/v1/usage/ai_scan")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "endpoint" in data
        assert data["endpoint"] == "ai_scan"
        assert "used" in data
        assert "limit" in data
        assert "remaining" in data
        assert "reset_at" in data
        assert "friendly_name" in data
    
    def test_get_endpoint_usage_unknown_endpoint(self, authenticated_client):
        """Getting usage for unknown endpoint uses default limits."""
        response = authenticated_client.get("/api/v1/usage/unknown_endpoint")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["limit"] == 100  # Default limit
    
    def test_get_endpoint_usage_unauthorized(self, client):
        """Getting endpoint usage without auth returns 401."""
        response = client.get("/api/v1/usage/ai_scan")
        
        assert response.status_code == 401