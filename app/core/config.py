from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "Plant IT"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    AWS_REGION: str = "eu-west-2"
    DYNAMODB_TABLE_NAME: str = "plant-it-plants"
    DYNAMODB_ENDPOINT_URL: str | None = None
    S3_BUCKET_NAME: str = "plant-it-images"
    
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "plant_it"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()