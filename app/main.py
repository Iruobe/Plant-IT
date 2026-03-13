from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(
    title="Plant IT API",
    description="AI-powered plant health analysis",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {
        # "message": "Welcome to Plant IT API", "docs": "/docs", 
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }