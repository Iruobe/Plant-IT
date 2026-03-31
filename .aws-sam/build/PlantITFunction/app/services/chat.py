import boto3
import json
from typing import Optional
from app.core.config import settings


def get_bedrock_client():
    return boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)


# In-memory chat history (replace with DynamoDB later)
chat_sessions = {}

SYSTEM_PROMPT = """You are Plant IT Assistant, a friendly and knowledgeable chatbot specializing in plants, gardening, and agriculture. 

Your expertise includes:
- Plant identification and care
- Diagnosing plant diseases and pests
- Gardening tips for all skill levels
- Vegetable and fruit growing
- Indoor and outdoor plant care
- Soil, composting, and fertilization
- Seasonal planting guides
- Sustainable and organic gardening practices

Guidelines:
- Be warm, encouraging, and supportive - gardening should be fun!
- Give practical, actionable advice
- If asked about something outside plants/agriculture, politely redirect to plant topics
- Use simple language but include scientific names when helpful
- If you're unsure, say so and suggest consulting a local nursery or extension service
- Keep responses concise but informative

Remember: You're helping people grow things and connect with nature. Be enthusiastic about their plant journey!"""


def chat_with_assistant(
    message: str, session_id: str = "default", plant_context: Optional[dict] = None
) -> dict:
    """Chat with the plant care assistant"""

    # Get or create session history
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []

    history = chat_sessions[session_id]

    # Build context if plant info provided
    context = ""
    if plant_context:
        context = f"\n\n[Context: The user has a {plant_context.get('name', 'plant')} ({plant_context.get('species', 'unknown species')}) with health status: {plant_context.get('health_status', 'unknown')}]"

    # Add user message to history
    user_message = message + context
    history.append({"role": "user", "content": user_message})

    # Keep only last 20 messages to manage context size
    if len(history) > 20:
        history = history[-20:]
        chat_sessions[session_id] = history

    client = get_bedrock_client()

    response = client.invoke_model(
        modelId="anthropic.claude-sonnet-4-6",
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": history,
            }
        ),
    )

    result = json.loads(response["body"].read())
    assistant_message = result["content"][0]["text"]

    # Add assistant response to history
    history.append({"role": "assistant", "content": assistant_message})
    chat_sessions[session_id] = history

    return {"response": assistant_message, "session_id": session_id}


def clear_chat_session(session_id: str = "default"):
    """Clear chat history for a session"""
    if session_id in chat_sessions:
        del chat_sessions[session_id]
    return {"message": "Chat session cleared"}
