from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from datetime import datetime

from app.repositories.dynamodb import get_plants_table
from app.repositories.s3 import generate_download_url
from app.services.bedrock import analyze_plant_image
from app.services.recommendations import get_plant_recommendations
from app.services.chat import chat_with_assistant, clear_chat_session
from app.core.auth import get_current_user
from app.repositories import care_plans as care_plans_repo
import uuid

router = APIRouter()


# Scan Models
class ScanRequest(BaseModel):
    plant_id: str


class ScanResult(BaseModel):
    scan_id: str
    plant_id: str
    plant_type: Optional[str] = None
    health_score: int
    health_status: str
    issues: List[str]
    recommendations: List[str]
    summary: str
    scanned_at: str


# Recommendation Models
class RecommendationRequest(BaseModel):
    goals: List[str] = []  # food, decorative, medicinal, commercial, low_maintenance
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    space_type: Optional[str] = None  # indoor, outdoor, balcony, garden
    sunlight: Optional[str] = None  # full_sun, partial_shade, shade
    experience_level: str = "beginner"


# Chat Models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    plant_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


# Scan Endpoint
@router.post("/scan", response_model=ScanResult)
async def scan_plant(
    request: ScanRequest,
    current_user: dict = Depends(get_current_user)
):
    """Scan a plant image and analyze its health using AI."""
    table = get_plants_table()
    response = table.get_item(
        Key={
            "user_id": current_user["uid"],
            "plant_id": request.plant_id
        }
    )
    
    if 'Item' not in response:
        raise HTTPException(status_code=404, detail="Plant not found")
    
    plant = response['Item']
    
    if not plant.get('image_url'):
        raise HTTPException(status_code=400, detail="No image uploaded for this plant")
    
    analysis = analyze_plant_image(plant['image_url'])
    
    scan_id = str(uuid4())
    scanned_at = datetime.utcnow().isoformat()
    
    table.update_item(
        Key={
            "user_id": current_user["uid"],
            "plant_id": request.plant_id
        },
        UpdateExpression="SET health_score = :score, health_status = :status, updated_at = :now",
        ExpressionAttributeValues={
            ":score": analysis['health_score'],
            ":status": analysis['health_status'],
            ":now": scanned_at
        }
    )

    # Auto-generate care plan after scan
    try:
        # Delete existing care plans
        care_plans_repo.delete_care_plans_for_plant(user_id, plant_id)
        
        # Generate new care plan based on scan results
        care_prompt = f"""Based on this plant scan, generate 3-5 specific care tasks.

Plant: {plant.get('name', 'Unknown')}
Species: {analysis.get('plant_type', 'Unknown')}
Health Score: {analysis.get('health_score', 50)}%
Issues Found: {', '.join(analysis.get('issues', []))}
AI Recommendations: {', '.join(analysis.get('recommendations', []))}

Generate tasks as JSON array:
[{{"task_type": "water|fertilize|sunlight|rotate|prune|mist|inspect", "title": "...", "description": "specific instructions with quantities", "frequency": "daily|weekly|2x_weekly|3x_weekly", "times_per_week": number, "priority": "high|medium|low"}}]

Only return the JSON array, nothing else."""

        care_response = bedrock.invoke_model(
            modelId=settings.BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": care_prompt}]
            })
        )
        
        care_result = json.loads(care_response['body'].read())
        care_text = care_result['content'][0]['text'].strip()
        
        # Clean JSON response
        if care_text.startswith("```"):
            care_text = care_text.split("```")[1]
            if care_text.startswith("json"):
                care_text = care_text[4:]
        
        tasks_data = json.loads(care_text.strip())
        
        for task_data in tasks_data:
            care_plans_repo.create_care_plan_task(
                user_id=user_id,
                task_id=f"task_{uuid.uuid4().hex[:8]}",
                plant_id=plant_id,
                plant_name=plant.get('name', 'Unknown'),
                task_type=task_data.get('task_type', 'other'),
                title=task_data.get('title', ''),
                description=task_data.get('description', ''),
                frequency=task_data.get('frequency', 'daily'),
                times_per_week=task_data.get('times_per_week', 7),
                priority=task_data.get('priority', 'medium')
            )
    except Exception as e:
        # Don't fail the scan if care plan generation fails
        print(f"Care plan generation failed: {e}")
    
    return ScanResult(
        scan_id=scan_id,
        plant_id=request.plant_id,
        plant_type=analysis.get('plant_type'),
        health_score=analysis['health_score'],
        health_status=analysis['health_status'],
        issues=analysis['issues'],
        recommendations=analysis['recommendations'],
        summary=analysis['summary'],
        scanned_at=scanned_at
    )


# Recommendation Endpoint
@router.post("/recommendations")
async def get_recommendations(
    request: RecommendationRequest,
    current_user: dict = Depends(get_current_user)
):
    """Get personalized plant recommendations based on goals, location, and conditions."""
    recommendations = get_plant_recommendations(
        goals=request.goals,
        latitude=request.latitude,
        longitude=request.longitude,
        space_type=request.space_type,
        sunlight=request.sunlight,
        experience_level=request.experience_level
    )
    
    return recommendations


# Chat Endpoints
@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """Chat with the Plant IT assistant about plants and gardening."""
    # Get plant context if plant_id provided
    plant_context = None
    if request.plant_id:
        table = get_plants_table()
        response = table.get_item(
            Key={
                "user_id": current_user["uid"],
                "plant_id": request.plant_id
            }
        )
        if 'Item' in response:
            plant = response['Item']
            plant_context = {
                "name": plant.get("name"),
                "species": plant.get("species"),
                "health_status": plant.get("health_status"),
                "health_score": plant.get("health_score")
            }
    
    # Prefix session_id with user_id for isolation between users
    user_session_id = f"{current_user['uid']}_{request.session_id}"
    
    result = chat_with_assistant(
        message=request.message,
        session_id=user_session_id,
        plant_context=plant_context
    )
    
    return ChatResponse(
        response=result["response"],
        session_id=request.session_id
    )


@router.delete("/chat/{session_id}")
async def clear_chat(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Clear chat history for a session."""
    user_session_id = f"{current_user['uid']}_{session_id}"
    return clear_chat_session(user_session_id)