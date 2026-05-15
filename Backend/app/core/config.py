import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_USER: str = os.getenv("DB_USER", "genovate")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "genovate123")
    DB_NAME: str = os.getenv("DB_NAME", "genovate")
    
    # Storage (MinIO / S3)
    S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", "localhost:9000")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "minioadmin")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "minioadmin")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "genovate-assets")
    S3_USE_SSL: bool = os.getenv("S3_USE_SSL", "false").lower() == "true"
    
    # EpistemicOS — REAL MODE now
    EPISTEMICOS_URL: str = os.getenv("EPISTEMICOS_URL", "http://epistemicos:8000")
    EPISTEMICOS_MOCK_MODE: bool = os.getenv("EPISTEMICOS_MOCK_MODE", "false").lower() == "true"
    EPISTEMICOS_API_KEY: str = os.getenv("EPISTEMICOS_API_KEY", "")
    EPISTEMICOS_TIMEOUT_INGEST: int = int(os.getenv("EPISTEMICOS_TIMEOUT_INGEST", "120"))
    EPISTEMICOS_TIMEOUT_SIMULATE: int = int(os.getenv("EPISTEMICOS_TIMEOUT_SIMULATE", "300"))

    # Feature flags for gradual rollout
    EPISTEMICOS_ENABLE_INGEST: bool = os.getenv("EPISTEMICOS_ENABLE_INGEST", "true").lower() == "true"
    EPISTEMICOS_ENABLE_SIMULATION: bool = os.getenv("EPISTEMICOS_ENABLE_SIMULATION", "true").lower() == "true"
    EPISTEMICOS_ENABLE_CXU: bool = os.getenv("EPISTEMICOS_ENABLE_CXU", "true").lower() == "true"
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # API
    API_VERSION: str = "v1"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

settings = Settings()
