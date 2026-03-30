"""
Unit tests for input validators.

Tests the validators module which sanitizes and validates all user input.
Each validator function is tested for:
- Valid inputs (should pass)
- Invalid inputs (should raise HTTPException)
- Edge cases (empty strings, max length, special characters)
"""

import pytest
from fastapi import HTTPException
from app.core.validators import (
    sanitize_string,
    validate_plant_name,
    validate_species,
    validate_location,
    validate_goal,
    validate_uuid,
    validate_chat_message,
    validate_session_id,
    MAX_LENGTHS,
    VALID_GOALS,
)


class TestSanitizeString:
    """Tests for the base sanitize_string function."""
    
    def test_strips_whitespace(self):
        """Leading/trailing whitespace should be removed."""
        result = sanitize_string("  hello world  ", 100, "test")
        assert result == "hello world"
    
    def test_removes_control_characters(self):
        """Control characters (except newlines) should be removed."""
        # \x00 is null, \x07 is bell - both should be stripped
        result = sanitize_string("hello\x00world\x07", 100, "test")
        assert result == "helloworld"
    
    def test_preserves_newlines(self):
        """Newlines should be preserved for multi-line content."""
        result = sanitize_string("line1\nline2\r\nline3", 100, "test")
        assert "\n" in result
    
    def test_raises_on_exceeding_max_length(self):
        """Strings exceeding max length should raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            sanitize_string("a" * 101, 100, "Test field")
        
        assert exc_info.value.status_code == 400
        assert "too long" in exc_info.value.detail.lower()
    
    def test_returns_empty_for_empty_input(self):
        """Empty strings should remain empty."""
        result = sanitize_string("", 100, "test")
        assert result == ""
    
    def test_handles_none_input(self):
        """None input should return None."""
        result = sanitize_string(None, 100, "test")
        assert result is None


class TestValidatePlantName:
    """Tests for plant name validation."""
    
    def test_valid_name(self):
        """Normal plant names should pass."""
        result = validate_plant_name("My Monstera")
        assert result == "My Monstera"
    
    def test_name_with_special_characters(self):
        """Names with special characters should pass."""
        result = validate_plant_name("Plant #1 (Kitchen)")
        assert result == "Plant #1 (Kitchen)"
    
    def test_strips_whitespace(self):
        """Whitespace should be stripped."""
        result = validate_plant_name("  Fern  ")
        assert result == "Fern"
    
    def test_empty_name_raises(self):
        """Empty names should raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_plant_name("")
        
        assert exc_info.value.status_code == 400
        assert "required" in exc_info.value.detail.lower()
    
    def test_whitespace_only_raises(self):
        """Whitespace-only names should raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_plant_name("   ")
        
        assert exc_info.value.status_code == 400
    
    def test_none_raises(self):
        """None should raise HTTPException."""
        with pytest.raises(HTTPException):
            validate_plant_name(None)
    
    def test_max_length_enforced(self):
        """Names exceeding 100 characters should raise."""
        long_name = "A" * 101
        with pytest.raises(HTTPException) as exc_info:
            validate_plant_name(long_name)
        
        assert exc_info.value.status_code == 400
        assert "too long" in exc_info.value.detail.lower()
    
    def test_exactly_max_length_passes(self):
        """Names at exactly max length should pass."""
        name = "A" * MAX_LENGTHS["plant_name"]
        result = validate_plant_name(name)
        assert len(result) == MAX_LENGTHS["plant_name"]


class TestValidateSpecies:
    """Tests for species validation (optional field)."""
    
    def test_valid_species(self):
        """Normal species names should pass."""
        result = validate_species("Monstera deliciosa")
        assert result == "Monstera deliciosa"
    
    def test_none_returns_none(self):
        """None should return None (field is optional)."""
        result = validate_species(None)
        assert result is None
    
    def test_empty_returns_none(self):
        """Empty string should return None."""
        result = validate_species("")
        assert result is None
    
    def test_max_length_enforced(self):
        """Species exceeding 150 characters should raise."""
        long_species = "A" * 151
        with pytest.raises(HTTPException):
            validate_species(long_species)


class TestValidateLocation:
    """Tests for location validation (optional field)."""
    
    def test_valid_location(self):
        """Normal locations should pass."""
        result = validate_location("Kitchen windowsill")
        assert result == "Kitchen windowsill"
    
    def test_none_returns_none(self):
        """None should return None (field is optional)."""
        result = validate_location(None)
        assert result is None
    
    def test_empty_returns_none(self):
        """Empty string should return None."""
        result = validate_location("")
        assert result is None


class TestValidateGoal:
    """Tests for goal validation (must be from allowed list)."""
    
    def test_valid_goals(self):
        """All valid goals should pass."""
        for goal in VALID_GOALS:
            result = validate_goal(goal)
            assert result == goal
    
    def test_case_insensitive(self):
        """Goals should be case-insensitive."""
        result = validate_goal("DECORATIVE")
        assert result == "decorative"
        
        result = validate_goal("Food")
        assert result == "food"
    
    def test_strips_whitespace(self):
        """Whitespace should be stripped."""
        result = validate_goal("  medicinal  ")
        assert result == "medicinal"
    
    def test_invalid_goal_raises(self):
        """Invalid goals should raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_goal("invalid_goal")
        
        assert exc_info.value.status_code == 400
        assert "Invalid goal" in exc_info.value.detail
    
    def test_empty_returns_default(self):
        """Empty goal should return default."""
        result = validate_goal("")
        assert result == "decorative"
    
    def test_none_returns_default(self):
        """None should return default."""
        result = validate_goal(None)
        assert result == "decorative"


class TestValidateUUID:
    """Tests for UUID format validation."""
    
    def test_valid_uuid(self):
        """Valid UUIDs should pass."""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = validate_uuid(valid_uuid, "Plant ID")
        assert result == valid_uuid
    
    def test_valid_uuid_uppercase(self):
        """Uppercase UUIDs should pass."""
        valid_uuid = "123E4567-E89B-12D3-A456-426614174000"
        result = validate_uuid(valid_uuid, "Plant ID")
        assert result == valid_uuid
    
    def test_strips_whitespace(self):
        """Whitespace should be stripped."""
        valid_uuid = "  123e4567-e89b-12d3-a456-426614174000  "
        result = validate_uuid(valid_uuid, "Plant ID")
        assert result.strip() == result
    
    def test_invalid_uuid_raises(self):
        """Invalid UUIDs should raise HTTPException."""
        invalid_uuids = [
            "not-a-uuid",
            "123e4567-e89b-12d3-a456",  # Too short
            "123e4567-e89b-12d3-a456-4266141740001",  # Too long
            "123g4567-e89b-12d3-a456-426614174000",  # Invalid character 'g'
        ]
        
        for invalid_uuid in invalid_uuids:
            with pytest.raises(HTTPException) as exc_info:
                validate_uuid(invalid_uuid, "Plant ID")
            
            assert exc_info.value.status_code == 400
    
    def test_empty_raises(self):
        """Empty UUIDs should raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("", "Plant ID")
        
        assert exc_info.value.status_code == 400
        assert "required" in exc_info.value.detail.lower()
    
    def test_none_raises(self):
        """None should raise HTTPException."""
        with pytest.raises(HTTPException):
            validate_uuid(None, "Plant ID")


class TestValidateChatMessage:
    """Tests for chat message validation."""
    
    def test_valid_message(self):
        """Normal messages should pass."""
        result = validate_chat_message("How do I care for my plant?")
        assert result == "How do I care for my plant?"
    
    def test_preserves_newlines(self):
        """Multi-line messages should preserve newlines."""
        message = "Line 1\nLine 2\nLine 3"
        result = validate_chat_message(message)
        assert "\n" in result
    
    def test_empty_raises(self):
        """Empty messages should raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_chat_message("")
        
        assert exc_info.value.status_code == 400
        assert "empty" in exc_info.value.detail.lower()
    
    def test_whitespace_only_raises(self):
        """Whitespace-only messages should raise HTTPException."""
        with pytest.raises(HTTPException):
            validate_chat_message("   ")
    
    def test_max_length_enforced(self):
        """Messages exceeding 2000 characters should raise."""
        long_message = "A" * 2001
        with pytest.raises(HTTPException) as exc_info:
            validate_chat_message(long_message)
        
        assert exc_info.value.status_code == 400


class TestValidateSessionId:
    """Tests for session ID validation."""
    
    def test_valid_session_id(self):
        """Valid session IDs should pass."""
        valid_ids = ["default", "session_123", "my-session", "Session123"]
        
        for session_id in valid_ids:
            result = validate_session_id(session_id)
            assert result == session_id
    
    def test_empty_returns_default(self):
        """Empty session ID should return 'default'."""
        result = validate_session_id("")
        assert result == "default"
    
    def test_none_returns_default(self):
        """None should return 'default'."""
        result = validate_session_id(None)
        assert result == "default"
    
    def test_invalid_characters_raise(self):
        """Session IDs with invalid characters should raise."""
        invalid_ids = [
            "session/123",   # Slash
            "session@123",   # At sign
            "session 123",   # Space
            "session.123",   # Dot
        ]
        
        for invalid_id in invalid_ids:
            with pytest.raises(HTTPException) as exc_info:
                validate_session_id(invalid_id)
            
            assert exc_info.value.status_code == 400
    
    def test_max_length_enforced(self):
        """Session IDs exceeding 100 characters should raise."""
        long_id = "a" * 101
        with pytest.raises(HTTPException):
            validate_session_id(long_id)