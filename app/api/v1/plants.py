from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from datetime import datetime

#DB
from app.repositories.dynamodb import get_plants_table

router = APIRouter()

# In-memory storage TO DO:replace with DynamoDB later
#plants_db: dict = {} UPDATE: CURENTLY REPLACED WITH DYNAMODB

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
    table = get_plants_table()
    plant_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    plant = {
        "plant_id": plant_id,
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
    
    table.put_item(Item=plant)
    return plant

@router.get("/", response_model=List[Plant])
async def list_plants():
    table = get_plants_table()
    response = table.scan()
    return response.get('Items', [])

@router.get("/{plant_id}", response_model=Plant)
async def get_plant(plant_id: str):
    table = get_plants_table()
    response = table.get_item(Key={"plant_id": plant_id})
    
    if 'Item' not in response:
        raise HTTPException(status_code=404, detail="Plant not found")
    return response['Item']

@router.delete("/{plant_id}")
async def delete_plant(plant_id: str):
    table = get_plants_table()
    
    # Check if exists
    response = table.get_item(Key={"plant_id": plant_id})
    if 'Item' not in response:
        raise HTTPException(status_code=404, detail="Plant not found")
    
    table.delete_item(Key={"plant_id": plant_id})
    return {"message": "Plant deleted"}