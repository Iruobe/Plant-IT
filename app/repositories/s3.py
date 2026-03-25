import boto3
from app.core.config import settings

_s3_client = None


def get_s3_client():
    """Get cached S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3', region_name=settings.AWS_REGION)
    return _s3_client


def generate_upload_url(key: str) -> str:
    """Generate a presigned URL for direct upload from the app."""
    s3 = get_s3_client()
    
    url = s3.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': settings.S3_BUCKET_NAME,
            'Key': key,
            'ContentType': 'image/jpeg'
        },
        ExpiresIn=300  # 5 minutes
    )
    
    return url


def generate_download_url(key: str) -> str:
    """Generate a presigned URL to view an image."""
    s3 = get_s3_client()
    
    url = s3.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': settings.S3_BUCKET_NAME,
            'Key': key
        },
        ExpiresIn=3600  # 1 hour
    )
    
    return url