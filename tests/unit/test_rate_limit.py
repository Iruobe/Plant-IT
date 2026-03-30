"""
Unit tests for rate limiting functionality.

Tests the rate limit module which tracks API usage per user/endpoint.
Tests cover:
- Rate limit configuration
- Usage tracking
- Limit enforcement
- Window reset logic
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from fastapi import HTTPException

from app.core.rate_limit import (
    RATE_LIMITS,
    get_rate_limit_config,
    check_rate_limit,
    get_usage,
)


class TestRateLimitConfig:
    """Tests for rate limit configuration."""

    def test_ai_scan_config(self):
        """AI scan should have correct limits."""
        max_requests, window_seconds, friendly_name = get_rate_limit_config("ai_scan")

        assert max_requests == 10
        assert window_seconds == 3600  # 1 hour
        assert friendly_name == "plant scans"

    def test_ai_chat_config(self):
        """AI chat should have correct limits."""
        max_requests, window_seconds, friendly_name = get_rate_limit_config("ai_chat")

        assert max_requests == 30
        assert window_seconds == 3600
        assert friendly_name == "chat messages"

    def test_ai_recommendations_config(self):
        """AI recommendations should have correct limits."""
        max_requests, window_seconds, friendly_name = get_rate_limit_config(
            "ai_recommendations"
        )

        assert max_requests == 10
        assert window_seconds == 3600
        assert friendly_name == "recommendations"

    def test_care_plans_generate_config(self):
        """Care plan generation should have correct limits."""
        max_requests, window_seconds, friendly_name = get_rate_limit_config(
            "care_plans_generate"
        )

        assert max_requests == 10
        assert window_seconds == 3600
        assert friendly_name == "care plan generations"

    def test_default_config(self):
        """Unknown endpoints should use default limits."""
        max_requests, window_seconds, friendly_name = get_rate_limit_config(
            "unknown_endpoint"
        )

        assert max_requests == 100
        assert window_seconds == 60
        assert friendly_name == "requests"

    def test_all_limits_have_friendly_names(self):
        """All configured limits should have friendly names."""
        for endpoint, config in RATE_LIMITS.items():
            assert len(config) == 3, f"{endpoint} missing friendly_name"
            assert isinstance(config[2], str), f"{endpoint} friendly_name not string"


class TestCheckRateLimit:
    """Tests for the check_rate_limit function."""

    @pytest.fixture
    def mock_rate_limits_table(self):
        """Mock DynamoDB rate limits table."""
        with patch("app.core.rate_limit.get_rate_limits_table") as mock:
            table = MagicMock()
            mock.return_value = table
            yield table

    def test_first_request_allowed(self, mock_rate_limits_table):
        """First request should always be allowed."""
        mock_rate_limits_table.update_item.return_value = {
            "Attributes": {"request_count": 1}
        }

        result = check_rate_limit("user123", "ai_scan")

        assert result["allowed"] is True
        assert result["remaining"] == 9  # 10 - 1
        assert result["used"] == 1
        assert result["limit"] == 10
        assert result["friendly_name"] == "plant scans"

    def test_at_limit_allowed(self, mock_rate_limits_table):
        """Request at exactly the limit should be allowed."""
        mock_rate_limits_table.update_item.return_value = {
            "Attributes": {"request_count": 10}
        }

        result = check_rate_limit("user123", "ai_scan")

        assert result["allowed"] is True
        assert result["remaining"] == 0

    def test_over_limit_raises(self, mock_rate_limits_table):
        """Request over the limit should raise HTTPException."""
        mock_rate_limits_table.update_item.return_value = {
            "Attributes": {"request_count": 11}
        }

        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit("user123", "ai_scan")

        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["error"] == "rate_limit_exceeded"
        assert "plant scans" in exc_info.value.detail["message"]

    def test_different_users_separate_limits(self, mock_rate_limits_table):
        """Different users should have separate rate limits."""
        call_count = 0

        def track_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return {"Attributes": {"request_count": 1}}

        mock_rate_limits_table.update_item.side_effect = track_calls

        check_rate_limit("user_a", "ai_scan")
        check_rate_limit("user_b", "ai_scan")

        # Should be two separate DynamoDB calls
        assert call_count == 2

        # Verify different user IDs in calls
        calls = mock_rate_limits_table.update_item.call_args_list
        assert calls[0][1]["Key"]["user_id"] == "user_a"
        assert calls[1][1]["Key"]["user_id"] == "user_b"

    def test_dynamodb_error_allows_request(self, mock_rate_limits_table):
        """DynamoDB errors should fail open (allow request)."""
        mock_rate_limits_table.update_item.side_effect = Exception("DynamoDB error")

        result = check_rate_limit("user123", "ai_scan")

        # Should allow request despite error
        assert result["allowed"] is True

    def test_reset_time_included(self, mock_rate_limits_table):
        """Response should include reset time."""
        mock_rate_limits_table.update_item.return_value = {
            "Attributes": {"request_count": 5}
        }

        result = check_rate_limit("user123", "ai_scan")

        assert "reset_at" in result
        assert result["reset_at"] is not None


class TestGetUsage:
    """Tests for the get_usage function (read-only)."""

    @pytest.fixture
    def mock_rate_limits_table(self):
        """Mock DynamoDB rate limits table."""
        with patch("app.core.rate_limit.get_rate_limits_table") as mock:
            table = MagicMock()
            mock.return_value = table
            yield table

    def test_returns_current_usage(self, mock_rate_limits_table):
        """Should return current usage without incrementing."""
        mock_rate_limits_table.get_item.return_value = {"Item": {"request_count": 5}}

        result = get_usage("user123", "ai_scan")

        assert result["used"] == 5
        assert result["limit"] == 10
        assert result["remaining"] == 5
        assert result["endpoint"] == "ai_scan"
        assert result["friendly_name"] == "plant scans"

    def test_returns_zero_for_new_user(self, mock_rate_limits_table):
        """New users should show 0 usage."""
        mock_rate_limits_table.get_item.return_value = {}  # No item found

        result = get_usage("new_user", "ai_scan")

        assert result["used"] == 0
        assert result["remaining"] == 10

    def test_does_not_increment(self, mock_rate_limits_table):
        """get_usage should not modify the database."""
        mock_rate_limits_table.get_item.return_value = {"Item": {"request_count": 5}}

        get_usage("user123", "ai_scan")

        # Should use get_item, not update_item
        mock_rate_limits_table.get_item.assert_called_once()
        mock_rate_limits_table.update_item.assert_not_called()
