"""
Unit tests for authentication module.

Tests the auth module which verifies Firebase tokens.
Tests cover:
- Token validation
- Error handling for different failure modes
- User info extraction
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from firebase_admin.auth import (
    ExpiredIdTokenError,
    RevokedIdTokenError,
    InvalidIdTokenError,
    CertificateFetchError,
)


class TestGetCurrentUser:
    """Tests for the get_current_user dependency."""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock HTTP authorization credentials."""
        credentials = MagicMock()
        credentials.credentials = "valid_token_123"
        return credentials
    
    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self, mock_credentials):
        """Valid tokens should return user info."""
        with patch("app.core.auth.auth.verify_id_token") as mock_verify:
            mock_verify.return_value = {
                "uid": "user123",
                "email": "test@example.com",
                "name": "Test User",
            }
            
            from app.core.auth import get_current_user
            result = await get_current_user(mock_credentials)
            
            assert result["uid"] == "user123"
            assert result["email"] == "test@example.com"
            assert result["name"] == "Test User"
    
    @pytest.mark.asyncio
    async def test_missing_credentials_raises(self):
        """Missing credentials should raise 401."""
        from app.core.auth import get_current_user
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"] == "missing_token"
    
    @pytest.mark.asyncio
    async def test_empty_token_raises(self):
        """Empty tokens should raise 401."""
        credentials = MagicMock()
        credentials.credentials = ""
        
        from app.core.auth import get_current_user
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"] == "empty_token"
    
    @pytest.mark.asyncio
    async def test_expired_token_raises(self, mock_credentials):
        """Expired tokens should raise 401 with specific error."""
        with patch("app.core.auth.auth.verify_id_token") as mock_verify:
            mock_verify.side_effect = ExpiredIdTokenError("Token expired", None)
            
            from app.core.auth import get_current_user
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials)
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail["error"] == "token_expired"
    
    @pytest.mark.asyncio
    async def test_revoked_token_raises(self, mock_credentials):
        """Revoked tokens should raise 401 with specific error."""
        with patch("app.core.auth.auth.verify_id_token") as mock_verify:
            mock_verify.side_effect = RevokedIdTokenError("Token revoked")
            
            from app.core.auth import get_current_user
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials)
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail["error"] == "token_revoked"
    
    @pytest.mark.asyncio
    async def test_invalid_token_raises(self, mock_credentials):
        """Invalid tokens should raise 401 with specific error."""
        with patch("app.core.auth.auth.verify_id_token") as mock_verify:
            mock_verify.side_effect = InvalidIdTokenError("Invalid token")
            
            from app.core.auth import get_current_user
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials)
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail["error"] == "invalid_token"
    
    @pytest.mark.asyncio
    async def test_certificate_fetch_error_raises_503(self, mock_credentials):
        """Certificate fetch errors should raise 503."""
        with patch("app.core.auth.auth.verify_id_token") as mock_verify:
            mock_verify.side_effect = CertificateFetchError("Cannot fetch certs", None)
            
            from app.core.auth import get_current_user
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials)
            
            assert exc_info.value.status_code == 503
            assert exc_info.value.detail["error"] == "auth_service_unavailable"