from fastapi import APIRouter
from app.api.v1 import plants, ai, care_plans,usage 

api_router = APIRouter()

api_router.include_router(plants.router, prefix="/plants", tags=["Plants"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI"])
api_router.include_router(care_plans.router, prefix="/care-plans", tags=["Care Plans"])
api_router.include_router(usage.router, prefix="/usage", tags=["Usage"])