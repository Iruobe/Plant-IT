from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from datetime import datetime

router = APIRouter()

# In-memory storage (replace with DynamoDB later)
plants_db: dict = {}

class PlantCreate(BaseModel):
    name: str
    species: Optional[str] = None
    goal: str = "decorative"
    location: Optional[str] = None

class Plant(BaseModel):
    plant_id: str
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
async def create_plant(data: PlantCreate):
    plant_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    plant = Plant(
        plant_id=plant_id,
        created_at=now,
        updated_at=now,
        **data.model_dump()
    )
    plants_db[plant_id] = plant
    return plant

@router.get("/", response_model=List[Plant])
async def list_plants():
    return list(plants_db.values())

@router.get("/{plant_id}", response_model=Plant)
async def get_plant(plant_id: str):
    if plant_id not in plants_db:
        raise HTTPException(status_code=404, detail="Plant not found")
    return plants_db[plant_id]

@router.delete("/{plant_id}")
async def delete_plant(plant_id: str):
    if plant_id not in plants_db:
        raise HTTPException(status_code=404, detail="Plant not found")
    del plants_db[plant_id]
    return {"message": "Plant deleted"}