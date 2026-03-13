import boto3
from app.core.config import settings

def get_s3_client():
    return boto3.client('s3', region_name=settings.AWS_REGION)

def generate_upload_url(plant_id: str, filename: str) -> dict:
    """Generate a presigned URL for direct upload from the app"""
    s3 = get_s3_client()
    key = f"plants/{plant_id}/{filename}"
    
    url = s3.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': settings.S3_BUCKET_NAME,
            'Key': key,
            'ContentType': 'image/jpeg'
        },
        ExpiresIn=300  # 5 minutes
    )
    
    return {
        "upload_url": url,
        "key": key
    }

def generate_download_url(key: str) -> str:
    """Generate a presigned URL to view an image"""
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