from fastapi import APIRouter
from app.api.v1 import plants, ai

api_router = APIRouter()

api_router.include_router(plants.router, prefix="/plants", tags=["Plants"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI"])