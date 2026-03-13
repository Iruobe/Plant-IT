from pydantic import BaseModel
from typing import Optional, List

class UserPreferences(BaseModel):
    user_id: str = "default"  # Single user for now
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    climate_zone: Optional[str] = None
    goals: List[str] = []  # food, decorative, medicinal, commercial, low_maintenance
    experience_level: str = "beginner"  # beginner, intermediate, expert
    space_type: Optional[str] = None  # indoor, outdoor, balcony, garden
    sunlight: Optional[str] = None  # full_sun, partial_shade, shade