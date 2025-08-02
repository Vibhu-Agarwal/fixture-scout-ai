# scout_service/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file at the earliest


class Settings:
    # Firestore
    FIRESTORE_DATABASE_NAME: str | None = os.getenv("FIRESTORE_DATABASE_NAME")

    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    LLM_MAX_OUTPUT_TOKENS: int = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "8192"))

    # Vertex AI
    GCP_PROJECT_ID: str | None = os.getenv("GOOGLE_CLOUD_PROJECT")
    GEMINI_MODEL_NAME_VERTEX: str = os.getenv(
        "GEMINI_MODEL_NAME_VERTEX", "gemini-2.5-flash-lite"
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
    USER_FEEDBACK_COLLECTION: str = "user_feedback"


# Instantiate settings to be imported by other modules
settings = Settings()
