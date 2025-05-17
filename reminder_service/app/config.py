# reminder_service/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Firestore
    FIRESTORE_DATABASE_NAME: str | None = os.getenv("FIRESTORE_DATABASE_NAME")
    REMINDERS_COLLECTION: str = "reminders"
    USERS_COLLECTION: str = "users"  # Used by scheduler part

    # Pub/Sub - Publisher (for scheduler part)
    GCP_PROJECT_ID: str | None = os.getenv("GCP_PROJECT_ID")
    EMAIL_NOTIFICATIONS_TOPIC_ID: str = os.getenv(
        "EMAIL_NOTIFICATIONS_TOPIC_ID", "email-notifications-topic"
    )
    PHONE_MOCK_NOTIFICATIONS_TOPIC_ID: str = os.getenv(
        "PHONE_MOCK_NOTIFICATIONS_TOPIC_ID", "mock-phone-call-notifications-topic"
    )

    # Pub/Sub - Subscriber (for status updater part)
    # This is the TOPIC it will subscribe to (via a subscription)
    NOTIFICATION_STATUS_UPDATE_TOPIC_ID_TO_SUBSCRIBE: str = os.getenv(
        "NOTIFICATION_STATUS_UPDATE_TOPIC_ID_TO_SUBSCRIBE",
        "notification-status-updates-topic",
    )
    # The actual SUBSCRIPTION ID will be created in GCP and might be passed as env var for the push endpoint.
    # For simplicity, we'll assume the endpoint is generic and Pub/Sub push config points to it.
    # The topic ID is what we ensure exists if this service also takes on that role.


settings = Settings()
