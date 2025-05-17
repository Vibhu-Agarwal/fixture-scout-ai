# notification_service/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    GCP_PROJECT_ID: str | None = os.getenv("GCP_PROJECT_ID")

    FIRESTORE_DATABASE_NAME: str | None = os.getenv("FIRESTORE_DATABASE_NAME")
    NOTIFICATION_LOG_COLLECTION: str = os.getenv(
        "NOTIFICATION_LOG_COLLECTION", "notification_log"
    )

    # Topic to publish status updates TO
    NOTIFICATION_STATUS_UPDATE_TOPIC_ID: str = os.getenv(
        "NOTIFICATION_STATUS_UPDATE_TOPIC_ID", "notification-status-updates-topic"
    )


settings = Settings()
