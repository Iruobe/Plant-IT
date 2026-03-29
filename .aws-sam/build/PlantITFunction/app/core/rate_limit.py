import boto3
from datetime import datetime, timedelta
from fastapi import HTTPException
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
# Format: endpoint_key -> (max_requests, window_seconds, friendly_name)
RATE_LIMITS = {
    # AI endpoints - expensive, strict limits
    "ai_scan": (2, 3600, "plant scans"),
    "ai_chat": (30, 3600, "chat messages"),
    "ai_recommendations": (10, 3600, "recommendations"),
    "care_plans_generate": (10, 3600, "care plan generations"),
    
    # Standard endpoints - more generous
    "default": (100, 60, "requests"),
}


def get_rate_limit_config(endpoint_key: str) -> tuple[int, int, str]:
    """Get rate limit config for an endpoint."""
    return RATE_LIMITS.get(endpoint_key, RATE_LIMITS["default"])


def get_usage(user_id: str, endpoint_key: str) -> dict:
    """
    Get current usage for a user/endpoint without incrementing.
    Useful for displaying usage in the app.
    """
    table = get_rate_limits_table()
    max_requests, window_seconds, friendly_name = get_rate_limit_config(endpoint_key)
    
    now = datetime.utcnow()
    window_start = now.replace(second=0, microsecond=0)
    
    # For hourly limits, align to the hour
    if window_seconds >= 3600:
        window_start = window_start.replace(minute=0)
    
    window_key = window_start.isoformat()
    reset_at = (window_start + timedelta(seconds=window_seconds)).isoformat()
    
    try:
        response = table.get_item(
            Key={
                'user_id': user_id,
                'endpoint_key': f"{endpoint_key}#{window_key}"
            }
        )
        
        current_count = int(response.get('Item', {}).get('request_count', 0))
        remaining = max(0, max_requests - current_count)
        
        return {
            "endpoint": endpoint_key,
            "used": current_count,
            "limit": max_requests,
            "remaining": remaining,
            "reset_at": reset_at,
            "friendly_name": friendly_name
        }
    except Exception as e:
        print(f"Failed to get usage: {e}")
        return {
            "endpoint": endpoint_key,
            "used": 0,
            "limit": max_requests,
            "remaining": max_requests,
            "reset_at": reset_at,
            "friendly_name": friendly_name
        }


def check_rate_limit(user_id: str, endpoint_key: str) -> dict:
    """
    Check and update rate limit for a user/endpoint combination.
    
    Returns dict with:
        - allowed: bool - whether request is allowed
        - remaining: int - remaining requests in window
        - limit: int - maximum requests in window
        - reset_at: str - when the window resets (ISO format)
        - friendly_name: str - human readable name for the limit
    
    Raises HTTPException 429 if rate limit exceeded.
    """
    table = get_rate_limits_table()
    max_requests, window_seconds, friendly_name = get_rate_limit_config(endpoint_key)

        # Debug log
    print(f"Rate limit check: user={user_id}, endpoint={endpoint_key}, limit={max_requests}")
    
    now = datetime.utcnow()
    window_start = now.replace(second=0, microsecond=0)
    
    # For hourly limits, align to the hour
    if window_seconds >= 3600:
        window_start = window_start.replace(minute=0)
    
    window_key = window_start.isoformat()
    
    # TTL for DynamoDB auto-cleanup (window + 1 hour buffer)
    ttl = int((now + timedelta(seconds=window_seconds + 3600)).timestamp())
    
    # Calculate reset time
    reset_at = (window_start + timedelta(seconds=window_seconds)).isoformat()
    
    try:
        # Atomic increment using UpdateItem
        response = table.update_item(
            Key={
                'user_id': user_id,
                'endpoint_key': f"{endpoint_key}#{window_key}"
            },
            UpdateExpression="SET request_count = if_not_exists(request_count, :zero) + :inc, "
                           "window_start = if_not_exists(window_start, :ws), "
                           "#ttl_attr = :ttl",
            ExpressionAttributeNames={
                '#ttl_attr': 'ttl'
            },
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
        
        if current_count > max_requests:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"You've used all your {friendly_name} for this hour.",
                    "used": current_count,
                    "limit": max_requests,
                    "remaining": 0,
                    "reset_at": reset_at,
                    "friendly_name": friendly_name
                }
            )
        
        return {
            "allowed": True,
            "used": current_count,
            "limit": max_requests,
            "remaining": remaining,
            "reset_at": reset_at,
            "friendly_name": friendly_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # If rate limiting fails, allow the request but log the error
        print(f"Rate limit check failed: {e}")
        return {
            "allowed": True,
            "used": 0,
            "limit": max_requests,
            "remaining": max_requests,
            "reset_at": reset_at,
            "friendly_name": friendly_name
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