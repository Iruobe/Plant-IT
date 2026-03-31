from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import uuid4
from datetime import datetime

from app.repositories.s3 import generate_upload_url, generate_download_url
from app.repositories.dynamodb import get_plants_table
from app.repositories import care_plans as care_plans_repo
from app.core.auth import get_current_user
from app.core.validators import (
    validate_plant_name,
    validate_species,
    validate_location,
    validate_goal,
)

router = APIRouter()


class PlantCreate(BaseModel):
    name: str
    species: Optional[str] = None
    goal: str = "decorative"
    location: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        return validate_plant_name(v)

    @field_validator("species")
    @classmethod
    def validate_species_field(cls, v):
        return validate_species(v)

    @field_validator("location")
    @classmethod
    def validate_location_field(cls, v):
        return validate_location(v)

    @field_validator("goal")
    @classmethod
    def validate_goal_field(cls, v):
        return validate_goal(v)


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
    data: PlantCreate, current_user: dict = Depends(get_current_user)
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
        "updated_at": now,
    }

    # Remove None values before saving to DynamoDB
    plant_clean = {k: v for k, v in plant.items() if v is not None}
    table.put_item(Item=plant_clean)

    return plant


# Updated the list_plants function to generate presigned URLs for images:
@router.get("/", response_model=List[Plant])
async def list_plants(current_user: dict = Depends(get_current_user)):
    """List all plants for the authenticated user."""
    table = get_plants_table()

    response = table.query(
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": current_user["uid"]},
    )

    plants = response.get("Items", [])
    
    # Generate presigned URLs for images
    for plant in plants:
        if plant.get("image_url"):
            plant["image_url"] = generate_download_url(plant["image_url"])
    
    return plants


# Updated the get_plant function:
@router.get("/{plant_id}", response_model=Plant)
async def get_plant(plant_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific plant by ID."""
    table = get_plants_table()
    response = table.get_item(
        Key={"user_id": current_user["uid"], "plant_id": plant_id}
    )

    if "Item" not in response:
        raise HTTPException(status_code=404, detail="Plant not found")

    plant = response["Item"]
    
    # Generate presigned URL for image
    if plant.get("image_url"):
        plant["image_url"] = generate_download_url(plant["image_url"])
    
    return plant


@router.get("/{plant_id}", response_model=Plant)
async def get_plant(plant_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific plant by ID."""
    table = get_plants_table()
    response = table.get_item(
        Key={"user_id": current_user["uid"], "plant_id": plant_id}
    )

    if "Item" not in response:
        raise HTTPException(status_code=404, detail="Plant not found")

    return response["Item"]


@router.delete("/{plant_id}")
async def delete_plant(plant_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a plant and its associated care plans."""
    user_id = current_user["uid"]
    table = get_plants_table()

    # Check if exists and belongs to user
    response = table.get_item(Key={"user_id": user_id, "plant_id": plant_id})

    if "Item" not in response:
        raise HTTPException(status_code=404, detail="Plant not found")

    # Delete associated care plans
    care_plans_repo.delete_care_plans_for_plant(user_id, plant_id)

    # Delete the plant
    table.delete_item(Key={"user_id": user_id, "plant_id": plant_id})

    return {"message": "Plant deleted"}


@router.post("/{plant_id}/upload-url")
async def get_upload_url(
    plant_id: str,
    filename: str = Query(default="photo.jpg"),
    current_user: dict = Depends(get_current_user),
):
    """Get a presigned URL to upload an image directly to S3."""
    # Validate filename
    if not filename or len(filename) > 100:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Only allow safe file extensions
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
        )

    table = get_plants_table()
    response = table.get_item(
        Key={"user_id": current_user["uid"], "plant_id": plant_id}
    )

    if "Item" not in response:
        raise HTTPException(status_code=404, detail="Plant not found")

    # Include user_id in S3 path for organization
    key = f"plants/{current_user['uid']}/{plant_id}/{filename}"
    upload_url = generate_upload_url(key)

    return {"upload_url": upload_url, "key": key}


@router.post("/{plant_id}/confirm-upload")
async def confirm_upload(
    plant_id: str, key: str = Query(...), current_user: dict = Depends(get_current_user)
):
    """Confirm upload and save image URL to plant record."""
    # Validate key format (should match expected pattern)
    if not key.startswith(f"plants/{current_user['uid']}/{plant_id}/"):
        raise HTTPException(status_code=400, detail="Invalid upload key")

    table = get_plants_table()
    response = table.get_item(
        Key={"user_id": current_user["uid"], "plant_id": plant_id}
    )

    if "Item" not in response:
        raise HTTPException(status_code=404, detail="Plant not found")

    image_url = generate_download_url(key)

    table.update_item(
        Key={"user_id": current_user["uid"], "plant_id": plant_id},
        UpdateExpression="SET image_url = :url, updated_at = :now",
        ExpressionAttributeValues={":url": key, ":now": datetime.utcnow().isoformat()},
    )

    return {"message": "Image uploaded", "image_url": image_url}
