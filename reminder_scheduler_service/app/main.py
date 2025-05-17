# reminder_scheduler_service/app/main.py
import logging
import os
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from google.cloud import pubsub_v1

from .utils.logging_config import setup_logging

setup_logging()  # Initialize logging configuration first

from .config import settings
from .firestore_client import get_firestore_client

# Import the new helper and service logic
from .pubsub_utils import ensure_pubsub_topic_exists
from .services.scheduler_logic import fetch_and_process_due_reminders


logger = logging.getLogger(__name__)

# Global clients, initialized during lifespan
# Note: firestore_client is fetched via get_firestore_client() when needed.
# pubsub_publisher_client can also be a global initialized in lifespan.
_pubsub_publisher_client: pubsub_v1.PublisherClient | None = None


def get_pubsub_publisher_client() -> pubsub_v1.PublisherClient:
    """Returns the initialized Pub/Sub publisher client."""
    if _pubsub_publisher_client is None:
        # This should not happen if lifespan ran correctly, but as a safeguard:
        logger.error("Pub/Sub publisher client accessed before initialization!")
        raise RuntimeError("Pub/Sub publisher client not initialized.")
    return _pubsub_publisher_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pubsub_publisher_client
    logger.info("Reminder Service (Scheduler) starting up...")
    try:
        get_firestore_client()  # Initializes Firestore client

        project_id_for_pubsub = settings.GCP_PROJECT_ID
        if not project_id_for_pubsub and not os.getenv("PUBSUB_EMULATOR_HOST"):
            logger.critical(
                "GCP_PROJECT_ID is not set for Pub/Sub in a non-emulator environment. Service will likely fail."
            )
            # Consider raising an error to prevent startup if this is a hard requirement
            # For now, allow startup but it will fail at runtime if Pub/Sub is used without project ID

        _pubsub_publisher_client = pubsub_v1.PublisherClient()
        logger.info("Firestore client and Pub/Sub Publisher client initialized.")

        if project_id_for_pubsub:  # Only attempt to ensure topics if project_id is set
            # Ensure topics exist
            topics_to_ensure = [
                settings.EMAIL_NOTIFICATIONS_TOPIC_ID,
                settings.PHONE_MOCK_NOTIFICATIONS_TOPIC_ID,
            ]
            for topic_id in topics_to_ensure:
                if topic_id:  # Ensure topic_id from settings is not empty/None
                    await ensure_pubsub_topic_exists(
                        _pubsub_publisher_client, project_id_for_pubsub, topic_id
                    )
        else:
            logger.warning(
                "GCP_PROJECT_ID not set. Skipping Pub/Sub topic auto-creation/check. Ensure topics exist manually if not using emulator with default project."
            )

    except Exception as e:
        logger.critical(
            f"Failed to initialize clients or Pub/Sub topics on startup: {e}",
            exc_info=True,
        )
    yield
    # PubSub PublisherClient does not typically require explicit close in recent versions for standard usage.
    logger.info("Reminder Service (Scheduler) shutting down...")


app = FastAPI(
    title="Reminder Service (Scheduler Component)",  # Updated title
    description="Checks for due reminders and publishes them to Pub/Sub topics.",
    version="0.1.1",  # Incremented version
    lifespan=lifespan,
)


@app.post("/scheduler/check-and-dispatch-reminders", status_code=200)
async def check_and_dispatch_reminders_endpoint():
    """
    API endpoint to check for due reminders and publish them to Pub/Sub.
    Intended to be called by Cloud Scheduler.
    """
    try:
        db = get_firestore_client()
        publisher = get_pubsub_publisher_client()  # Get the initialized client

        # Delegate the core logic to the service function
        summary = await fetch_and_process_due_reminders(db, publisher)
        return summary
    except RuntimeError as e:  # e.g., if clients weren't initialized
        logger.critical(
            f"Service runtime error during scheduled task: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=503, detail=f"Service not ready or misconfigured: {str(e)}"
        )  # Service Unavailable
    except Exception as e:
        logger.critical(
            f"Scheduler Endpoint: Critical error during reminder publish check: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Reminder publish check failed due to an internal error: {str(e)}",
        )


@app.get("/")
async def read_root():
    return {
        "message": "Welcome to the Fixture Scout AI - Reminder Service (Scheduler Component)"
    }


@app.get("/health")
async def health_check():
    db_ok = False
    pubsub_ok = False
    try:
        get_firestore_client()  # Checks if Firestore client can be retrieved
        db_ok = True
    except Exception:
        logger.warning("Health check: Firestore client not healthy.")

    try:
        get_pubsub_publisher_client()  # Checks if PubSub client can be retrieved
        pubsub_ok = True
    except Exception:
        logger.warning("Health check: PubSub publisher client not healthy.")

    if db_ok and pubsub_ok:
        return {
            "status": "ok",
            "firestore_healthy": True,
            "pubsub_publisher_initialized": True,
        }
    else:
        details = []
        if not db_ok:
            details.append("Firestore client issue.")
        if not pubsub_ok:
            details.append("PubSub client issue.")
        return {
            "status": "degraded",
            "firestore_healthy": db_ok,
            "pubsub_publisher_initialized": pubsub_ok,
            "detail": " ".join(details) or "One or more components are not healthy.",
        }
