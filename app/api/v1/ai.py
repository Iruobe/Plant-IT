from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4

from datetime import datetime
from app.repositories.dynamodb import get_plants_table
from app.repositories.s3 import generate_download_url
from app.services.bedrock import analyze_plant_image

from app.services.recommendations import get_plant_recommendations
from app.services.chat import chat_with_assistant, clear_chat_session


router = APIRouter()

#Scan Models
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

#Recommendation Models
class RecommendationRequest(BaseModel):
    goals: List[str] = []  # food, decorative, medicinal, commercial, low_maintenance
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    space_type: Optional[str] = None  # indoor, outdoor, balcony, garden
    sunlight: Optional[str] = None  # full_sun, partial_shade, shade
    experience_level: str = "beginner"



#Chat Models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    plant_id: Optional[str] = None  # Optional: provide context about a specific plant

class ChatResponse(BaseModel):
    response: str
    session_id: str



#Scan Endpoint
@router.post("/scan", response_model=ScanResult)
async def scan_plant(request: ScanRequest):
    """Scan a plant image and analyze its health using AI"""
    
    
    table = get_plants_table()
    response = table.get_item(Key={"plant_id": request.plant_id})
    
    if 'Item' not in response:
        raise HTTPException(status_code=404, detail="Plant not found")
    
    plant = response['Item']
    
    if not plant.get('image_url'):
        raise HTTPException(status_code=400, detail="No image uploaded for this plant")
   
    
   
    analysis = analyze_plant_image(plant['image_url'])
    
    scan_id = str(uuid4())
    scanned_at = datetime.utcnow().isoformat()
    
    
    table.update_item(
        Key={"plant_id": request.plant_id},
        UpdateExpression="SET health_score = :score, health_status = :status, updated_at = :now",
        ExpressionAttributeValues={
            ":score": analysis['health_score'],
            ":status": analysis['health_status'],
            ":now": scanned_at
        }
    )
    
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

#Recommendation Endpoints
@router.post("/recommendations")
async def get_recommendations(request: RecommendationRequest):
    """Get personalized plant recommendations based on goals, location, and conditions"""
    
    recommendations = get_plant_recommendations(
        goals=request.goals,
        latitude=request.latitude,
        longitude=request.longitude,
        space_type=request.space_type,
        sunlight=request.sunlight,
        experience_level=request.experience_level
    )
    
    return recommendations

#Chat Endpoints
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with the Plant IT assistant about plants and gardening"""
    
    # Get plant context if plant_id provided
    plant_context = None
    if request.plant_id:
        table = get_plants_table()
        response = table.get_item(Key={"plant_id": request.plant_id})
        if 'Item' in response:
            plant = response['Item']
            plant_context = {
                "name": plant.get("name"),
                "species": plant.get("species"),
                "health_status": plant.get("health_status"),
                "health_score": plant.get("health_score")
            }
    
    result = chat_with_assistant(
        message=request.message,
        session_id=request.session_id,
        plant_context=plant_context
    )
    
    return ChatResponse(
        response=result["response"],
        session_id=result["session_id"]
    )

@router.delete("/chat/{session_id}")
async def clear_chat(session_id: str):
    """Clear chat history for a session"""
    return clear_chat_session(session_id)