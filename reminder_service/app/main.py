# reminder_service/app/main.py
import logging
import os
from fastapi import (
    FastAPI,
    HTTPException,
    Body,
    BackgroundTasks,
)
from contextlib import asynccontextmanager
from google.cloud import pubsub_v1
from pydantic import ValidationError  # Import for specific error catching

from .utils.logging_config import setup_logging

setup_logging()

from .config import settings
from .firestore_client import get_firestore_client
from .pubsub_utils import ensure_pubsub_topic_exists
from .services.scheduler_logic import fetch_and_process_due_reminders
from .services.status_updater_logic import process_reminder_status_update
from .models import NotificationStatusUpdatePayload, PubSubPushMessage

logger = logging.getLogger(__name__)

_pubsub_publisher_client: pubsub_v1.PublisherClient | None = None


def get_pubsub_publisher_client() -> pubsub_v1.PublisherClient:
    """Returns the initialized Pub/Sub publisher client."""
    if _pubsub_publisher_client is None:
        logger.error("Pub/Sub publisher client accessed before initialization!")
        raise RuntimeError("Pub/Sub publisher client not initialized.")
    return _pubsub_publisher_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pubsub_publisher_client
    logger.info("Reminder Service starting up...")
    try:
        get_firestore_client()
        project_id_for_pubsub = settings.GCP_PROJECT_ID

        if not project_id_for_pubsub and not os.getenv("PUBSUB_EMULATOR_HOST"):
            logger.critical(
                "GCP_PROJECT_ID is not set for Pub/Sub in a non-emulator environment."
            )
            # Consider raising an error to prevent startup if this is a hard requirement
            # For now, allow startup but it will fail at runtime if Pub/Sub is used without project ID

        _pubsub_publisher_client = pubsub_v1.PublisherClient()
        logger.info("Firestore client and Pub/Sub Publisher client initialized.")

        if project_id_for_pubsub:
            # Topics for the SCHEDULER part to PUBLISH to
            scheduler_topics_to_ensure = [
                settings.EMAIL_NOTIFICATIONS_TOPIC_ID,
                settings.PHONE_MOCK_NOTIFICATIONS_TOPIC_ID,
            ]
            for topic_id in scheduler_topics_to_ensure:
                if topic_id:
                    await ensure_pubsub_topic_exists(
                        _pubsub_publisher_client, project_id_for_pubsub, topic_id
                    )

            # Topic for the STATUS UPDATER part to SUBSCRIBE to (ensure it exists if this service is also responsible)
            # The NotificationService also tries to create this. It's okay if both try; `ensure_pubsub_topic_exists` handles `AlreadyExists`.
            if settings.NOTIFICATION_STATUS_UPDATE_TOPIC_ID_TO_SUBSCRIBE:
                await ensure_pubsub_topic_exists(
                    _pubsub_publisher_client,  # Can use same publisher client to check/create
                    project_id_for_pubsub,
                    settings.NOTIFICATION_STATUS_UPDATE_TOPIC_ID_TO_SUBSCRIBE,
                )
        else:
            logger.warning(
                "GCP_PROJECT_ID not set. Skipping Pub/Sub topic auto-creation/check."
            )

    except Exception as e:
        logger.critical(
            f"Failed to initialize clients or Pub/Sub topics on startup: {e}",
            exc_info=True,
        )
    yield
    logger.info("Reminder Service shutting down...")


app = FastAPI(
    title="Reminder Service",  # Updated title
    description="Handles scheduling reminders (publishing to Pub/Sub) and updating reminder statuses from Pub/Sub.",
    version="0.2.0",
    lifespan=lifespan,
)


# --- Scheduler Endpoint ---
@app.post("/scheduler/check-and-dispatch-reminders", status_code=200)
async def check_and_dispatch_reminders_endpoint():
    """
    API endpoint for the scheduler component to check for due reminders and publish them.
    """
    try:
        db = get_firestore_client()
        publisher = get_pubsub_publisher_client()
        summary = await fetch_and_process_due_reminders(db, publisher)
        return summary
    except RuntimeError as e:
        logger.critical(
            f"Scheduler Endpoint: Service runtime error: {e}", exc_info=True
        )
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")
    except Exception as e:
        logger.critical(f"Scheduler Endpoint: Critical error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# --- Status Updater Endpoint (Pub/Sub Push Target) ---
@app.post(
    "/reminders/handle-status-update", status_code=204
)  # 204 No Content for Pub/Sub ack
async def handle_reminder_status_update_push(
    request_body: PubSubPushMessage = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Handles notification status updates pushed from Pub/Sub.
    (Target for a push subscription to 'notification-status-updates-topic')
    """
    logger.info(
        f"StatusUpdater: Received Pub/Sub push on subscription: {request_body.subscription}"
    )
    db = get_firestore_client()

    try:
        decoded_payload_dict = request_body.decode_data()
        status_update_payload = NotificationStatusUpdatePayload(**decoded_payload_dict)
    except (ValueError, ValidationError) as e:
        logger.error(
            f"StatusUpdater: Failed to decode/validate Pub/Sub message data: {e}",
            exc_info=True,
        )
        # Acknowledge the message to prevent redelivery of malformed data.
        # Consider sending to a dead-letter queue if this happens frequently.
        return  # Implicit 204

    # Process the status update in the background to quickly ack the Pub/Sub message
    background_tasks.add_task(process_reminder_status_update, db, status_update_payload)
    logger.info(
        f"StatusUpdater: Status update for reminder {status_update_payload.original_reminder_id} handed off to background task."
    )
    return  # Implicit 204


# --- Root and Health Check ---
@app.get("/")
async def read_root():
    return {"message": "Welcome to the Fixture Scout AI - Reminder Service"}


@app.get("/health")
async def health_check():
    db_ok = False
    pubsub_ok = False
    try:
        get_firestore_client()
        db_ok = True
    except Exception:
        logger.warning("Health check: Firestore client not healthy.")
    try:
        get_pubsub_publisher_client()  # Checks if publisher client can be retrieved
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
