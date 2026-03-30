from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router

from contextlib import asynccontextmanager
from app.repositories.dynamodb import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    create_tables()
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="Plant IT API",
    description="AI-powered plant health analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# TO DO: CORS - allow all origins for now (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
    }
