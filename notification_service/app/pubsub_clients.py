# notification_service/app/pubsub_clients.py
import logging
import os
from google.cloud import pubsub_v1
from .config import settings

logger = logging.getLogger(__name__)
publisher: pubsub_v1.PublisherClient | None = None


def get_publisher_client() -> pubsub_v1.PublisherClient:
    global publisher
    if publisher is None:
        if not os.getenv("PUBSUB_EMULATOR_HOST") and not settings.GCP_PROJECT_ID:
            logger.critical(
                "GCP_PROJECT_ID is not set. Pub/Sub Publisher will likely fail outside emulator."
            )
            # This should ideally be caught at app startup more forcefully
        publisher = pubsub_v1.PublisherClient()
        logger.info("Pub/Sub Publisher client initialized for Notification Service.")
    return publisher


# We will also need the _ensure_pubsub_topic_exists logic here for the status update topic
# Or ensure it's created by another means (e.g. manually for P1, or by ReminderStatusUpdaterService)
# For now, let's assume it will be created.
