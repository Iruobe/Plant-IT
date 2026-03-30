import re
from typing import Optional
from fastapi import HTTPException

# Maximum lengths for user inputs
MAX_LENGTHS = {
    "plant_name": 100,
    "species": 150,
    "location": 100,
    "goal": 50,
    "chat_message": 2000,
    "session_id": 100,
}

# Valid goal values
VALID_GOALS = {
    "decorative",
    "food",
    "medicinal",
    "air_purifying",
    "commercial",
    "low_maintenance",
}

# UUID pattern
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def sanitize_string(value: str, max_length: int, field_name: str) -> str:
    """
    Sanitize a string input:
    - Strip whitespace
    - Limit length
    - Remove control characters
    """
    if not value:
        return value

    # Strip whitespace
    value = value.strip()

    # Remove control characters (except newlines for chat)
    value = "".join(char for char in value if char.isprintable() or char in "\n\r\t")

    # Check length
    if len(value) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} is too long. Maximum {max_length} characters allowed.",
        )

    return value


def validate_plant_name(name: str) -> str:
    """Validate and sanitize plant name."""
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Plant name is required.")

    return sanitize_string(name, MAX_LENGTHS["plant_name"], "Plant name")


def validate_species(species: Optional[str]) -> Optional[str]:
    """Validate and sanitize species (optional)."""
    if not species:
        return None

    return sanitize_string(species, MAX_LENGTHS["species"], "Species")


def validate_location(location: Optional[str]) -> Optional[str]:
    """Validate and sanitize location (optional)."""
    if not location:
        return None

    return sanitize_string(location, MAX_LENGTHS["location"], "Location")


def validate_goal(goal: str) -> str:
    """Validate goal is from allowed values."""
    if not goal:
        return "decorative"  # Default

    goal = goal.lower().strip()

    if goal not in VALID_GOALS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid goal. Must be one of: {', '.join(VALID_GOALS)}",
        )

    return goal


def validate_uuid(value: str, field_name: str = "ID") -> str:
    """Validate UUID format."""
    if not value:
        raise HTTPException(status_code=400, detail=f"{field_name} is required.")

    value = value.strip()

    if not UUID_PATTERN.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format.")

    return value


def validate_chat_message(message: str) -> str:
    """Validate and sanitize chat message."""
    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    return sanitize_string(message, MAX_LENGTHS["chat_message"], "Message")


def validate_session_id(session_id: Optional[str]) -> str:
    """Validate and sanitize session ID."""
    if not session_id:
        return "default"

    # Only allow alphanumeric, underscore, hyphen
    session_id = session_id.strip()
    if not re.match(r"^[a-zA-Z0-9_-]+$", session_id):
        raise HTTPException(
            status_code=400,
            detail="Session ID can only contain letters, numbers, underscores, and hyphens.",
        )

    return sanitize_string(session_id, MAX_LENGTHS["session_id"], "Session ID")
