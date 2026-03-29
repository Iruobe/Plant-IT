from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from datetime import datetime

from app.repositories.s3 import generate_upload_url, generate_download_url
from app.repositories.dynamodb import get_plants_table
from app.core.auth import get_current_user

router = APIRouter()


class PlantCreate(BaseModel):
    name: str
    species: Optional[str] = None
    goal: str = "decorative"
    location: Optional[str] = None


class Plant(BaseModel):
    plant_id: str
    user_id: str
    name: str
    species: Optional[str] = None
    goal: str
    location: Optional[str] = None
    health_status: str = "unknown"
    health_score: Optional[int] = None
    image_url: Optional[str] = None
    created_at: str
    updated_at: str


@router.post("/", response_model=Plant, status_code=201)
async def create_plant(
    data: PlantCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new plant for the authenticated user."""
    table = get_plants_table()
    plant_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    plant = {
        "plant_id": plant_id,
        "user_id": current_user["uid"],
        "name": data.name,
        "species": data.species,
        "goal": data.goal,
        "location": data.location,
        "health_status": "unknown",
        "health_score": None,
        "image_url": None,
        "created_at": now,
        "updated_at": now
    }
    
    # Remove None values before saving to DynamoDB
    plant_clean = {k: v for k, v in plant.items() if v is not None}
    table.put_item(Item=plant_clean)
    
    return plant


@router.get("/", response_model=List[Plant])
async def list_plants(current_user: dict = Depends(get_current_user)):
    """List all plants for the authenticated user."""
    table = get_plants_table()
    
    # Query only this user's plants (not scan entire table)
    response = table.query(
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": current_user["uid"]}
    )
    
    return response.get('Items', [])


@router.get("/{plant_id}", response_model=Plant)
async def get_plant(
    plant_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific plant by ID."""
    table = get_plants_table()
    response = table.get_item(
        Key={
            "user_id": current_user["uid"],
            "plant_id": plant_id
        }
    )
    
    if 'Item' not in response:
        raise HTTPException(status_code=404, detail="Plant not found")
    
    return response['Item']


@router.delete("/{plant_id}")
async def delete_plant(
    plant_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a plant."""
    table = get_plants_table()
    
    # Check if exists and belongs to user
    response = table.get_item(
        Key={
            "user_id": current_user["uid"],
            "plant_id": plant_id
        }
    )
    
    if 'Item' not in response:
        raise HTTPException(status_code=404, detail="Plant not found")
    
    table.delete_item(
        Key={
            "user_id": current_user["uid"],
            "plant_id": plant_id
        }
    )
    
    return {"message": "Plant deleted"}


@router.post("/{plant_id}/upload-url")
async def get_upload_url(
    plant_id: str,
    filename: str = Query(default="photo.jpg"),
    current_user: dict = Depends(get_current_user)
):
    """Get a presigned URL to upload an image directly to S3."""
    table = get_plants_table()
    response = table.get_item(
        Key={
            "user_id": current_user["uid"],
            "plant_id": plant_id
        }
    )
    
    if 'Item' not in response:
        raise HTTPException(status_code=404, detail="Plant not found")
    
    # Include user_id in S3 path for organization
    key = f"plants/{current_user['uid']}/{plant_id}/{filename}"
    upload_url = generate_upload_url(key)
    
    return {"upload_url": upload_url, "key": key}


@router.post("/{plant_id}/confirm-upload")
async def confirm_upload(
    plant_id: str,
    key: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Confirm upload and save image URL to plant record."""
    table = get_plants_table()
    response = table.get_item(
        Key={
            "user_id": current_user["uid"],
            "plant_id": plant_id
        }
    )
    
    if 'Item' not in response:
        raise HTTPException(status_code=404, detail="Plant not found")
    
    image_url = generate_download_url(key)
    
    table.update_item(
        Key={
            "user_id": current_user["uid"],
            "plant_id": plant_id
        },
        UpdateExpression="SET image_url = :url, updated_at = :now",
        ExpressionAttributeValues={
            ":url": key,
            ":now": datetime.utcnow().isoformat()
        }
    )
    
    return {"message": "Image uploaded", "image_url": image_url}