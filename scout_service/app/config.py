# scout_service/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file at the earliest


class Settings:
    # Firestore
    FIRESTORE_DATABASE_NAME: str | None = os.getenv("FIRESTORE_DATABASE_NAME")

    # Vertex AI
    GCP_PROJECT_ID: str | None = os.getenv("GCP_PROJECT_ID")
    GCP_REGION: str | None = os.getenv("GCP_REGION")
    GEMINI_MODEL_NAME_VERTEX: str = os.getenv(
        "GEMINI_MODEL_NAME_VERTEX", "gemini-1.5-flash"
    )

    # Application Specific
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    FIXTURE_LOOKOUT_WINDOW_DAYS: int = int(
        os.getenv("FIXTURE_LOOKOUT_WINDOW_DAYS", "14")
    )

    # Firestore Collection Names (can be centralized here)
    USERS_COLLECTION: str = "users"
    USER_PREFERENCES_COLLECTION: str = "user_preferences"
    FIXTURES_COLLECTION: str = "fixtures"
    REMINDERS_COLLECTION: str = "reminders"


# Instantiate settings to be imported by other modules
settings = Settings()
