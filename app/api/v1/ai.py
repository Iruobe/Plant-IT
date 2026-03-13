from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4

from datetime import datetime
from app.repositories.dynamodb import get_plants_table
from app.repositories.s3 import generate_download_url
from app.services.bedrock import analyze_plant_image

router = APIRouter()

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

class AskRequest(BaseModel):
    question: str
    plant_id: Optional[str] = None

class AskResponse(BaseModel):
    answer: str
    sources: List[str] = []

@router.post("/scan", response_model=ScanResult)
async def scan_plant(request: ScanRequest):
    """Scan a plant image and analyze its health using AI"""
    
    # Get the plant
    table = get_plants_table()
    response = table.get_item(Key={"plant_id": request.plant_id})
    
    if 'Item' not in response:
        raise HTTPException(status_code=404, detail="Plant not found")
    
    plant = response['Item']
    
    if not plant.get('image_url'):
        raise HTTPException(status_code=400, detail="No image uploaded for this plant")
    
    # Get the image URL
    image_url = generate_download_url(plant['image_url'])
    
    # Analyze with Bedrock
    # analysis = analyze_plant_image(image_url)

    # Analyze with Bedrock (pass the S3 key, not URL)
    analysis = analyze_plant_image(plant['image_url'])
    
    scan_id = str(uuid4())
    scanned_at = datetime.utcnow().isoformat()
    
    # Update plant with latest health status
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

@router.post("/ask", response_model=AskResponse)
async def ask_assistant(request: AskRequest):
    # TODO: Implement with MongoDB + Bedrock
    return AskResponse(
        answer=f"This is a placeholder answer for: {request.question}",
        sources=["plant-care-guide.md"]
    )