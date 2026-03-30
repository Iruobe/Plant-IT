"""
Shared test fixtures and configuration.

This file contains:
- Mocked AWS services (DynamoDB, S3, Bedrock)
- Test client for FastAPI
- Authentication fixtures
- Sample data generators
"""

import pytest
import boto3
import json
import os
from unittest.mock import Mock, patch, MagicMock
from moto import mock_aws
from fastapi.testclient import TestClient
from datetime import datetime
from uuid import uuid4

# Set test environment before importing app
os.environ["ENVIRONMENT"] = "test"
os.environ["AWS_REGION"] = "eu-west-2"
os.environ["DYNAMODB_TABLE_NAME"] = "plant-it-plants-test"
os.environ["CARE_PLANS_TABLE_NAME"] = "plant-it-care-plans-test"
os.environ["TASK_COMPLETIONS_TABLE_NAME"] = "plant-it-task-completions-test"
os.environ["RATE_LIMITS_TABLE_NAME"] = "plant-it-rate-limits-test"
os.environ["S3_BUCKET_NAME"] = "plant-it-images-test"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"


# ============================================================
# DATABASE FIXTURES
# ============================================================


@pytest.fixture(scope="function")
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-west-2"


@pytest.fixture(scope="function")
def mock_dynamodb(aws_credentials):
    """
    Create mocked DynamoDB tables for testing.

    Creates all 4 tables used by the app:
    - Plants table
    - Care plans table
    - Task completions table
    - Rate limits table

    Each table is empty at the start of each test.
    """
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-2")

        # Plants table
        dynamodb.create_table(
            TableName="plant-it-plants-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "plant_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "plant_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Care plans table
        dynamodb.create_table(
            TableName="plant-it-care-plans-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "task_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "task_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Task completions table
        dynamodb.create_table(
            TableName="plant-it-task-completions-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "completion_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "completion_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Rate limits table
        dynamodb.create_table(
            TableName="plant-it-rate-limits-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "endpoint_key", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "endpoint_key", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield dynamodb


@pytest.fixture(scope="function")
def mock_s3(aws_credentials):
    """
    Create mocked S3 bucket for testing.

    Creates the images bucket with proper configuration.
    """
    with mock_aws():
        s3 = boto3.client("s3", region_name="eu-west-2")
        s3.create_bucket(
            Bucket="plant-it-images-test",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        yield s3


# ============================================================
# AUTHENTICATION FIXTURES
# ============================================================


@pytest.fixture
def mock_firebase_user():
    """
    Returns a mock decoded Firebase token.

    Simulates a verified user from Firebase Auth.
    """
    return {
        "uid": "test_user_123",
        "email": "testuser@example.com",
        "name": "Test User",
        "email_verified": True,
    }


@pytest.fixture
def mock_firebase_user_2():
    """Second test user for multi-user tests."""
    return {
        "uid": "test_user_456",
        "email": "another@example.com",
        "name": "Another User",
        "email_verified": True,
    }


@pytest.fixture
def auth_headers():
    """
    Returns authorization headers with a mock token.

    The token itself doesn't matter since we mock Firebase verification.
    """
    return {"Authorization": "Bearer mock_firebase_token_12345"}


@pytest.fixture
def mock_auth(mock_firebase_user):
    """
    Mock Firebase authentication.

    Patches the get_current_user dependency to return our test user
    without actually calling Firebase.
    """
    with patch("app.core.auth.auth.verify_id_token") as mock_verify:
        mock_verify.return_value = mock_firebase_user
        yield mock_verify


# ============================================================
# FASTAPI TEST CLIENT
# ============================================================


@pytest.fixture
def client(mock_dynamodb, mock_s3, mock_auth):
    """
    FastAPI test client with all mocks configured.

    This client:
    - Uses mocked DynamoDB tables
    - Uses mocked S3 bucket
    - Bypasses Firebase authentication
    - Resets app state between tests
    """
    # Reset cached DynamoDB connections
    from app.repositories import dynamodb as db_module
    from app.core import rate_limit as rl_module

    db_module._dynamodb = None
    db_module._plants_table = None
    rl_module._dynamodb = None
    rl_module._rate_limits_table = None

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client, auth_headers):
    """
    Test client with authentication headers pre-configured.

    Usage:
        def test_something(authenticated_client):
            response = authenticated_client.get("/api/v1/plants/")
    """
    client.headers.update(auth_headers)
    return client


# ============================================================
# SAMPLE DATA FIXTURES
# ============================================================


@pytest.fixture
def sample_plant_data():
    """
    Returns valid plant creation data.

    Use this to create plants in tests.
    """
    return {
        "name": "Test Monstera",
        "species": "Monstera deliciosa",
        "goal": "decorative",
        "location": "Living room",
    }


@pytest.fixture
def sample_plant_minimal():
    """Minimal valid plant data (only required fields)."""
    return {
        "name": "Simple Plant",
        "goal": "decorative",
    }


@pytest.fixture
def sample_chat_message():
    """Sample chat request data."""
    return {
        "message": "How often should I water my monstera?",
        "session_id": "test_session",
    }


@pytest.fixture
def sample_care_task():
    """Sample care plan task."""
    return {
        "task_id": f"task_{uuid4().hex[:8]}",
        "plant_id": str(uuid4()),
        "plant_name": "Test Plant",
        "task_type": "water",
        "title": "Water the plant",
        "description": "Water thoroughly until drainage",
        "frequency": "weekly",
        "times_per_week": 2,
        "priority": "high",
    }


# ============================================================
# MOCK AI SERVICES
# ============================================================


@pytest.fixture
def mock_bedrock():
    """
    Mock AWS Bedrock AI service.

    Returns predefined responses for:
    - Plant scanning (health analysis)
    - Care plan generation
    - Chat responses
    """
    mock_response = {
        "content": [
            {
                "text": json.dumps(
                    {
                        "plant_type": "Monstera deliciosa",
                        "health_score": 85,
                        "health_status": "healthy",
                        "issues": ["Minor dust on leaves"],
                        "recommendations": [
                            "Wipe leaves monthly",
                            "Rotate for even growth",
                        ],
                        "summary": "Your plant is healthy with minor care needs.",
                    }
                )
            }
        ]
    }

    with patch("app.services.bedrock.get_bedrock_client") as mock_client:
        mock_invoke = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(mock_response).encode()
        mock_invoke.return_value = {"body": mock_body}
        mock_client.return_value.invoke_model = mock_invoke
        yield mock_client


@pytest.fixture
def mock_bedrock_care_plan():
    """Mock Bedrock response specifically for care plan generation."""
    care_tasks = [
        {
            "task_type": "water",
            "title": "Water your Monstera",
            "description": "Water when top 2 inches of soil are dry",
            "frequency": "weekly",
            "times_per_week": 2,
            "priority": "high",
        },
        {
            "task_type": "mist",
            "title": "Mist the leaves",
            "description": "Spray leaves with water to increase humidity",
            "frequency": "2x_weekly",
            "times_per_week": 2,
            "priority": "medium",
        },
    ]

    mock_response = {"content": [{"text": json.dumps(care_tasks)}]}

    with patch("app.services.bedrock.get_bedrock_client") as mock_client:
        mock_invoke = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(mock_response).encode()
        mock_invoke.return_value = {"body": mock_body}
        mock_client.return_value.invoke_model = mock_invoke
        yield mock_client


# ============================================================
# HELPER FUNCTIONS
# ============================================================


@pytest.fixture
def create_test_plant(authenticated_client, sample_plant_data):
    """
    Factory fixture to create plants in tests.

    Usage:
        def test_something(create_test_plant):
            plant = create_test_plant()
            # plant is now in the database
    """

    def _create_plant(data=None):
        plant_data = data or sample_plant_data
        response = authenticated_client.post("/api/v1/plants/", json=plant_data)
        assert response.status_code == 201
        return response.json()

    return _create_plant


@pytest.fixture
def create_test_care_task(mock_dynamodb, mock_firebase_user):
    """
    Factory fixture to create care tasks directly in DynamoDB.

    Bypasses API for faster test setup.
    """

    def _create_task(plant_id=None, **overrides):
        task_id = f"task_{uuid4().hex[:8]}"
        plant_id = plant_id or str(uuid4())

        task = {
            "user_id": mock_firebase_user["uid"],
            "task_id": task_id,
            "plant_id": plant_id,
            "plant_name": "Test Plant",
            "task_type": "water",
            "title": "Water the plant",
            "description": "Water thoroughly",
            "frequency": "daily",
            "times_per_week": 7,
            "priority": "medium",
            "active": True,
            "created_at": datetime.utcnow().isoformat(),
            **overrides,
        }

        table = mock_dynamodb.Table("plant-it-care-plans-test")
        table.put_item(Item=task)
        return task

    return _create_task


# ============================================================
# PERFORMANCE TEST FIXTURES
# ============================================================


@pytest.fixture
def response_time_threshold():
    """
    Maximum acceptable response times in milliseconds.

    Based on 50 concurrent users target.
    """
    return {
        "health_check": 100,  # Simple endpoint
        "list_plants": 300,  # Database read
        "create_plant": 500,  # Database write
        "get_plant": 200,  # Single item read
        "delete_plant": 400,  # Database delete
        "scan_plant": 5000,  # AI operation (Bedrock)
        "chat": 3000,  # AI operation
        "today_tasks": 400,  # Database query
        "complete_task": 300,  # Database update
    }
