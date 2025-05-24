# user_management_service/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    FIRESTORE_DATABASE_NAME: str | None = os.getenv("FIRESTORE_DATABASE_NAME")
    GCP_PROJECT_ID: str | None = os.getenv("GCP_PROJECT_ID")

    # Firestore Collection Names
    USERS_COLLECTION: str = "users"
    USER_PREFERENCES_COLLECTION: str = "user_preferences"
    REMINDERS_COLLECTION: str = "reminders"  # For querying reminders
    FIXTURES_COLLECTION: str = "fixtures"  # For enriching reminder data
    USER_FEEDBACK_COLLECTION: str = "user_feedback"
    # JWT Settings
    # !!! CHANGE THIS IN YOUR .env FOR PRODUCTION !!!
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", "your-super-secret-and-long-random-key-please-change"
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )  # 30 minutes
    # JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_MINUTES", "10080")) # 7 days (for refresh tokens, if implemented)

    # Google OAuth Client ID (from your GCP Credentials page for your web application)
    # This is used by the backend to verify the audience of the Google ID Token.
    # The UI will also use this (or a different client ID for its platform if separate).
    GOOGLE_CLIENT_ID: str | None = os.getenv("GOOGLE_CLIENT_ID")


settings = Settings()

if settings.JWT_SECRET_KEY == "your-super-secret-and-long-random-key-please-change":
    import logging  # Can't use global logger before it's configured if this check is at module level

    logging.warning(
        "CRITICAL: JWT_SECRET_KEY is set to the default insecure value. Please change it in your .env file!"
    )
if not settings.GOOGLE_CLIENT_ID:
    import logging

    logging.warning(
        "WARNING: GOOGLE_CLIENT_ID is not set. Google ID Token verification might fail or be insecure."
    )
