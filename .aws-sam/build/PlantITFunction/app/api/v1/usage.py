from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.core.rate_limit import get_usage

router = APIRouter()


@router.get("/")
async def get_user_usage(current_user: dict = Depends(get_current_user)):
    """Get current usage for all rate-limited endpoints."""
    user_id = current_user["uid"]

    # Get usage for each rate-limited endpoint
    endpoints = ["ai_scan", "ai_chat", "ai_recommendations", "care_plans_generate"]

    usage_data = {}
    for endpoint in endpoints:
        usage_data[endpoint] = get_usage(user_id, endpoint)

    return {"user_id": user_id, "usage": usage_data}


@router.get("/{endpoint_key}")
async def get_endpoint_usage(
    endpoint_key: str, current_user: dict = Depends(get_current_user)
):
    """Get current usage for a specific endpoint."""
    user_id = current_user["uid"]
    return get_usage(user_id, endpoint_key)
