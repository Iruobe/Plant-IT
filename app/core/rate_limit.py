import boto3
from datetime import datetime, timedelta
from fastapi import HTTPException, Request
from typing import Optional
from app.core.config import settings

# Cache DynamoDB resource
_dynamodb = None
_rate_limits_table = None


def get_dynamodb():
    """Get cached DynamoDB resource."""
    global _dynamodb
    if _dynamodb is None:
        if settings.DYNAMODB_ENDPOINT_URL and settings.ENVIRONMENT == "development":
            _dynamodb = boto3.resource(
                'dynamodb',
                region_name=settings.AWS_REGION,
                endpoint_url=settings.DYNAMODB_ENDPOINT_URL,
                aws_access_key_id='dummyAccount',
                aws_secret_access_key='dummyAccount'
            )
        else:
            _dynamodb = boto3.resource(
                'dynamodb',
                region_name=settings.AWS_REGION
            )
    return _dynamodb


def get_rate_limits_table():
    """Get cached rate limits table."""
    global _rate_limits_table
    if _rate_limits_table is None:
        db = get_dynamodb()
        _rate_limits_table = db.Table(settings.RATE_LIMITS_TABLE_NAME)
    return _rate_limits_table


# Rate limit configurations
# Format: endpoint_key -> (max_requests, window_seconds)
RATE_LIMITS = {
    # AI endpoints - expensive, strict limits
    "ai_scan": (10, 3600),           # 10 per hour
    "ai_chat": (30, 3600),           # 30 per hour
    "ai_recommendations": (10, 3600), # 10 per hour
    "care_plans_generate": (10, 3600), # 10 per hour
    
    # Standard endpoints - more generous
    "default": (100, 60),            # 100 per minute
}


def get_rate_limit_config(endpoint_key: str) -> tuple[int, int]:
    """Get rate limit config for an endpoint."""
    return RATE_LIMITS.get(endpoint_key, RATE_LIMITS["default"])


def check_rate_limit(user_id: str, endpoint_key: str) -> dict:
    """
    Check and update rate limit for a user/endpoint combination.
    
    Returns dict with:
        - allowed: bool - whether request is allowed
        - remaining: int - remaining requests in window
        - reset_at: str - when the window resets (ISO format)
    
    Raises HTTPException 429 if rate limit exceeded.
    """
    table = get_rate_limits_table()
    max_requests, window_seconds = get_rate_limit_config(endpoint_key)
    
    now = datetime.utcnow()
    window_start = now.replace(second=0, microsecond=0)
    
    # For hourly limits, align to the hour
    if window_seconds >= 3600:
        window_start = window_start.replace(minute=0)
    
    window_key = window_start.isoformat()
    
    # TTL for DynamoDB auto-cleanup (window + 1 hour buffer)
    ttl = int((now + timedelta(seconds=window_seconds + 3600)).timestamp())
    
    try:
        # Atomic increment using UpdateItem
        response = table.update_item(
            Key={
                'user_id': user_id,
                'endpoint_key': f"{endpoint_key}#{window_key}"
            },
            UpdateExpression="SET request_count = if_not_exists(request_count, :zero) + :inc, "
                           "window_start = if_not_exists(window_start, :ws), "
                           "ttl = :ttl",
            ExpressionAttributeValues={
                ':zero': 0,
                ':inc': 1,
                ':ws': window_key,
                ':ttl': ttl
            },
            ReturnValues='ALL_NEW'
        )
        
        current_count = int(response['Attributes']['request_count'])
        remaining = max(0, max_requests - current_count)
        reset_at = (window_start + timedelta(seconds=window_seconds)).isoformat()
        
        if current_count > max_requests:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {max_requests} per {window_seconds // 60} minutes.",
                    "remaining": 0,
                    "reset_at": reset_at
                }
            )
        
        return {
            "allowed": True,
            "remaining": remaining,
            "reset_at": reset_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # If rate limiting fails, allow the request but log the error
        print(f"Rate limit check failed: {e}")
        return {
            "allowed": True,
            "remaining": -1,
            "reset_at": None
        }


def rate_limit(endpoint_key: str):
    """
    Dependency for rate limiting endpoints.
    
    Usage:
        @router.post("/scan")
        async def scan_plant(
            ...,
            _rate_limit: dict = Depends(rate_limit("ai_scan"))
        ):
    """
    from fastapi import Depends
    from app.core.auth import get_current_user
    
    async def check(current_user: dict = Depends(get_current_user)):
        return check_rate_limit(current_user["uid"], endpoint_key)
    
    return check