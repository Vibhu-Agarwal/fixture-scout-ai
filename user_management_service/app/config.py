# user_management_service/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    FIRESTORE_DATABASE_NAME: str | None = os.getenv("FIRESTORE_DATABASE_NAME")

    # Firestore Collection Names
    USERS_COLLECTION: str = "users"
    USER_PREFERENCES_COLLECTION: str = "user_preferences"
    REMINDERS_COLLECTION: str = "reminders"  # For querying reminders
    FIXTURES_COLLECTION: str = "fixtures"  # For enriching reminder data
    USER_FEEDBACK_COLLECTION: str = "user_feedback"


settings = Settings()
