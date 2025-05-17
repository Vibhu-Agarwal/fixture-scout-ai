# reminder_scheduler_service/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Firestore
    FIRESTORE_DATABASE_NAME: str | None = os.getenv("FIRESTORE_DATABASE_NAME")
    REMINDERS_COLLECTION: str = "reminders"
    USERS_COLLECTION: str = "users"

    # Pub/Sub
    GCP_PROJECT_ID: str | None = os.getenv("GCP_PROJECT_ID") # Needed for constructing full topic paths
    EMAIL_NOTIFICATIONS_TOPIC_ID: str = os.getenv("EMAIL_NOTIFICATIONS_TOPIC_ID", "email-notifications-topic")
    PHONE_MOCK_NOTIFICATIONS_TOPIC_ID: str = os.getenv("PHONE_MOCK_NOTIFICATIONS_TOPIC_ID", "mock-phone-call-notifications-topic")
    
    # NOTIFICATION_SERVICE_URL is no longer needed here as we publish to Pub/Sub

settings = Settings()
