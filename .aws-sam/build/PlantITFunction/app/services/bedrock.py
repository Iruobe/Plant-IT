import boto3
import base64
import json
from app.core.config import settings


def get_bedrock_client():
    return boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)


def get_s3_client():
    return boto3.client("s3", region_name=settings.AWS_REGION)


def analyze_plant_image(image_key: str) -> dict:
    """Analyze a plant image using Claude Vision"""

    # Download image directly from S3
    s3 = get_s3_client()
    response = s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=image_key)
    image_bytes = response["Body"].read()
    image_data = base64.b64encode(image_bytes).decode("utf-8")

    # Get content type from S3 metadata
    content_type = response.get("ContentType", "image/jpeg")

    # Ensure it's a valid type for Claude
    valid_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if content_type not in valid_types:
        content_type = "image/jpeg"

    client = get_bedrock_client()

    prompt = """You are a plant health expert. Analyze this plant image and provide:

1. **Plant Identification**: What type of plant is this? (if identifiable)
2. **Health Score**: Rate the plant's health from 0-100
3. **Health Status**: One of: healthy, mild_issues, moderate_issues, severe_issues, critical
4. **Issues Found**: List any problems you can see (yellowing, spots, wilting, pests, etc.)
5. **Recommendations**: Specific care advice to improve the plant's health

Respond in this exact JSON format:
{
    "plant_type": "string",
    "health_score": number,
    "health_status": "string",
    "issues": ["string"],
    "recommendations": ["string"],
    "summary": "A brief 1-2 sentence summary"
}"""

    response = client.invoke_model(
        modelId="anthropic.claude-sonnet-4-6",
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": content_type,
                                    "data": image_data,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            }
        ),
    )

    result = json.loads(response["body"].read())
    text_response = result["content"][0]["text"]

    # Parse the JSON from Claude's response
    try:
        start = text_response.find("{")
        end = text_response.rfind("}") + 1
        analysis = json.loads(text_response[start:end])
    except Exception:
        analysis = {
            "plant_type": "Unknown",
            "health_score": 50,
            "health_status": "unknown",
            "issues": ["Could not analyze image"],
            "recommendations": ["Please try again with a clearer image"],
            "summary": text_response,
        }

    return analysis
