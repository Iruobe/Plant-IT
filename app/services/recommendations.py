import boto3
import json
import httpx
from typing import Optional, List
from app.core.config import settings


def get_bedrock_client():
    return boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)


def get_weather_data(lat: float, lon: float) -> dict:
    """Get current weather and climate info from Open-Meteo (free, no API key)"""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto"
        response = httpx.get(url, timeout=10)
        data = response.json()

        return {
            "current_temp": data.get("current", {}).get("temperature_2m"),
            "humidity": data.get("current", {}).get("relative_humidity_2m"),
            "temp_max": data.get("daily", {}).get("temperature_2m_max", [None])[0],
            "temp_min": data.get("daily", {}).get("temperature_2m_min", [None])[0],
            "precipitation": data.get("daily", {}).get("precipitation_sum", [None])[0],
            "timezone": data.get("timezone"),
        }
    except Exception as e:
        return {"error": str(e)}


def estimate_climate_zone(lat: float, lon: float, weather: dict) -> str:
    """Estimate USDA-style hardiness zone based on location and weather"""
    # Simplified climate zone estimation
    abs_lat = abs(lat)

    if abs_lat < 10:
        return "tropical"
    elif abs_lat < 25:
        return "subtropical"
    elif abs_lat < 40:
        if weather.get("temp_min", 10) < 0:
            return "temperate_cold"
        return "temperate_warm"
    elif abs_lat < 55:
        return "cool_temperate"
    else:
        return "cold"


def get_plant_recommendations(
    goals: List[str],
    latitude: Optional[float],
    longitude: Optional[float],
    space_type: Optional[str] = None,
    sunlight: Optional[str] = None,
    experience_level: str = "beginner",
) -> dict:
    """Get AI-powered plant recommendations based on user preferences and location"""

    # Get weather data if location provided
    weather = {}
    climate_zone = "unknown"

    if latitude and longitude:
        weather = get_weather_data(latitude, longitude)
        if "error" not in weather:
            climate_zone = estimate_climate_zone(latitude, longitude, weather)

    client = get_bedrock_client()

    prompt = f"""You are an expert horticulturist and agricultural advisor. Based on the following user preferences and conditions, recommend suitable plants to grow.

**User Preferences:**
- Goals: {', '.join(goals) if goals else 'general gardening'}
- Experience Level: {experience_level}
- Space Type: {space_type or 'not specified'}
- Sunlight Available: {sunlight or 'not specified'}

**Location & Climate:**
- Climate Zone: {climate_zone}
- Current Temperature: {weather.get('current_temp', 'unknown')}°C
- Humidity: {weather.get('humidity', 'unknown')}%
- Recent Precipitation: {weather.get('precipitation', 'unknown')}mm

Provide 5-8 plant recommendations. For each plant include:
1. Common name and scientific name
2. Why it suits their goals and conditions
3. Difficulty level (easy/medium/hard)
4. Key care tips
5. Expected time to harvest/bloom

Respond in this JSON format:
{{
    "climate_summary": "Brief description of their climate conditions",
    "recommendations": [
        {{
            "common_name": "string",
            "scientific_name": "string",
            "match_reason": "why this plant suits them",
            "difficulty": "easy/medium/hard",
            "care_tips": ["tip1", "tip2"],
            "time_to_harvest": "string",
            "goal_match": ["which goals it matches"]
        }}
    ],
    "general_advice": "Overall gardening advice for their situation"
}}"""

    response = client.invoke_model(
        modelId="anthropic.claude-sonnet-4-6",
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            }
        ),
    )

    result = json.loads(response["body"].read())
    text_response = result["content"][0]["text"]

    try:
        start = text_response.find("{")
        end = text_response.rfind("}") + 1
        recommendations = json.loads(text_response[start:end])
    except:
        recommendations = {
            "climate_summary": "Could not determine climate",
            "recommendations": [],
            "general_advice": text_response,
        }

    # Add weather data to response
    recommendations["weather"] = weather
    recommendations["climate_zone"] = climate_zone

    return recommendations
