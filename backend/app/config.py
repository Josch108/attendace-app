import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root if present
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")

class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Smart Attendance System")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Database connection URL (defaults to local SQLite or PostgreSQL)
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{ROOT_DIR / 'attendance.db'}")
    
    # Local storage directory for student face images
    STORAGE_PATH: Path = (ROOT_DIR / os.getenv("STORAGE_PATH", str(ROOT_DIR / "data" / "students"))).resolve()
    
    # Model and attendance policy parameters
    ABSENCE_TIMEOUT_SECONDS: int = int(os.getenv("ABSENCE_TIMEOUT_SECONDS", "45"))
    FACE_MATCH_THRESHOLD: float = float(os.getenv("FACE_MATCH_THRESHOLD", "0.50"))
    FACE_CONFIRMATION_COUNT: int = int(os.getenv("FACE_CONFIRMATION_COUNT", "3"))
    MODEL_VERSION: str = os.getenv("MODEL_VERSION", "insightface/buffalo_l")

settings = Settings()
