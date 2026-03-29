import boto3
from app.core.config import settings

_dynamodb = None
_plants_table = None


def get_dynamodb():
    """Get cached DynamoDB resource."""
    global _dynamodb
    if _dynamodb is None:
        if settings.DYNAMODB_ENDPOINT_URL and settings.ENVIRONMENT == "development":
            # Local DynamoDB for development
            _dynamodb = boto3.resource(
                'dynamodb',
                region_name=settings.AWS_REGION,
                endpoint_url=settings.DYNAMODB_ENDPOINT_URL,
                aws_access_key_id='dummyAccount',
                aws_secret_access_key='dummyAccount'
            )
        else:
            # Real AWS DynamoDB for production
            _dynamodb = boto3.resource(
                'dynamodb',
                region_name=settings.AWS_REGION
            )
    return _dynamodb


def get_plants_table():
    """Get cached plants table."""
    global _plants_table
    if _plants_table is None:
        db = get_dynamodb()
        _plants_table = db.Table(settings.DYNAMODB_TABLE_NAME)
    return _plants_table


def create_tables():
    """Create tables if they don't exist (for local dev)."""
    if settings.ENVIRONMENT != "development":
        return  # Don't create tables in production - use Terraform/SAM
    
    db = get_dynamodb()
    
    existing_tables = [t.name for t in db.tables.all()]
    
    if settings.DYNAMODB_TABLE_NAME not in existing_tables:
        db.create_table(
            TableName=settings.DYNAMODB_TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                {'AttributeName': 'plant_id', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'plant_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print(f"Created table: {settings.DYNAMODB_TABLE_NAME}")
        