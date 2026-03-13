import boto3
from app.core.config import settings

def get_dynamodb():
    return boto3.resource(
        'dynamodb',
        region_name=settings.AWS_REGION,
        endpoint_url=settings.DYNAMODB_ENDPOINT_URL,
        aws_access_key_id='dummyAccount',
        aws_secret_access_key='dummyAccount'
    )

def create_tables():
    """Create tables if they don't exist (for local dev)"""
    db = get_dynamodb()
    
    existing_tables = [t.name for t in db.tables.all()]
    
    if settings.DYNAMODB_TABLE_NAME not in existing_tables:
        db.create_table(
            TableName=settings.DYNAMODB_TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'plant_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'plant_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print(f"Created table: {settings.DYNAMODB_TABLE_NAME}")

def get_plants_table():
    db = get_dynamodb()
    return db.Table(settings.DYNAMODB_TABLE_NAME)