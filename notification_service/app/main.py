# notification_service/app/main.py
import logging
import datetime
import json  # For Pub/Sub message data
import uuid  # For generating notification_log_id
from fastapi import FastAPI, HTTPException, Request, Body, BackgroundTasks
from pydantic import ValidationError
from contextlib import asynccontextmanager
from google.cloud import pubsub_v1
from google.api_core.exceptions import (
    NotFound as PubSubTopicNotFound,
    AlreadyExists as PubSubTopicAlreadyExists,
)


from .utils.logging_config import setup_logging

setup_logging()  # Initialize logging configuration first

from .config import settings
from .firestore_client import get_firestore_client
from .pubsub_clients import (
    get_publisher_client,
)  # Import publisher client for status updates
from .models import PubSubMessage, PubSubMessageData, NotificationLogDoc
from .services.mock_senders import get_sender, INotificationSender

logger = logging.getLogger(__name__)


# --- Lifespan for client initialization ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Notification Service starting up...")
    try:
        get_firestore_client()
        publisher = get_publisher_client()  # Initializes the publisher client

        # Ensure the status update topic exists
        if settings.GCP_PROJECT_ID and settings.NOTIFICATION_STATUS_UPDATE_TOPIC_ID:
            topic_path = publisher.topic_path(
                settings.GCP_PROJECT_ID, settings.NOTIFICATION_STATUS_UPDATE_TOPIC_ID
            )
            try:
                publisher.get_topic(topic=topic_path)
                logger.info(
                    f"Pub/Sub topic '{topic_path}' for status updates already exists."
                )
            except PubSubTopicNotFound:
                logger.info(
                    f"Pub/Sub topic '{topic_path}' for status updates not found. Creating it..."
                )
                try:
                    publisher.create_topic(name=topic_path)
                    logger.info(
                        f"Pub/Sub topic '{topic_path}' for status updates created successfully."
                    )
                except (
                    PubSubTopicAlreadyExists
                ):  # Should not happen if get_topic failed with NotFound
                    logger.info(
                        f"Pub/Sub topic '{topic_path}' for status updates was created by another process."
                    )
                except Exception as e_create:
                    logger.error(
                        f"Failed to create Pub/Sub status update topic '{topic_path}': {e_create}",
                        exc_info=True,
                    )
                    # Decide if this is critical enough to stop startup
        else:
            logger.warning(
                "GCP_PROJECT_ID or NOTIFICATION_STATUS_UPDATE_TOPIC_ID not set, skipping status topic check/creation."
            )

        logger.info(
            "Firestore and Pub/Sub Publisher clients initialized successfully for Notification Service."
        )
    except Exception as e:
        logger.critical(
            f"Failed to initialize clients or Pub/Sub topics on startup: {e}",
            exc_info=True,
        )
    yield
    logger.info("Notification Service shutting down...")


app = FastAPI(
    title="Notification Service",
    description="Consumes notification requests from Pub/Sub, (mock) sends them, and logs status.",
    version="0.1.0",
    lifespan=lifespan,
)


# --- Helper Functions ---
async def _log_notification_attempt(
    db: firestore.Client,
    payload: PubSubMessageData,
    status: str,
    contact_target: str | None = None,
    error_message: str | None = None,
    log_id_override: str | None = None,  # For updating an existing log
) -> str:
    """Logs the notification attempt to Firestore and returns the log ID."""
    log_id = log_id_override or str(uuid.uuid4())
    log_doc_ref = db.collection(settings.NOTIFICATION_LOG_COLLECTION).document(log_id)

    log_data = NotificationLogDoc(
        notification_log_id=log_id,
        original_reminder_id=payload.original_reminder_id,
        user_id=payload.user_id,
        reminder_mode=payload.reminder_mode,
        status=status,
        contact_target=contact_target or payload.contact_email or payload.contact_phone,
        message_content_snippet=payload.message_content[:100],  # Store a snippet
        error_message=error_message,
        # attempt_count will be handled if we implement retries; for now, it's 1
    )
    if status not in [
        "processing",
        "failed_payload_decode",
    ]:  # Mark processed_at for terminal statuses
        log_data.processed_at = datetime.datetime.now(datetime.timezone.utc)

    if log_id_override:  # Update existing document
        update_dict = log_data.model_dump(exclude_unset=True, exclude_none=True)
        # Ensure critical fields like status and timestamps are always updated
        update_dict["status"] = status
        update_dict["last_attempt_utc"] = datetime.datetime.now(datetime.timezone.utc)
        if log_data.processed_at:
            update_dict["processed_at"] = log_data.processed_at
        if error_message:
            update_dict["error_message"] = error_message

        log_doc_ref.update(update_dict)
        logger.info(f"Updated notification log for {log_id} with status: {status}")
    else:  # Create new document
        log_doc_ref.set(log_data.model_dump())
        logger.info(
            f"Created notification log for {log_id} with initial status: {status}"
        )
    return log_id


async def _publish_status_update(
    original_reminder_id: str,
    final_status: str,  # e.g., "delivered_mock", "failed_provider"
    user_id: str,
    reminder_mode: str,
    error_detail: str | None = None,
):
    """Publishes the final notification status to the status update topic."""
    publisher = get_publisher_client()
    if (
        not publisher
        or not settings.GCP_PROJECT_ID
        or not settings.NOTIFICATION_STATUS_UPDATE_TOPIC_ID
    ):
        logger.error(
            "Cannot publish status update: Publisher client or config missing."
        )
        return

    topic_path = publisher.topic_path(
        settings.GCP_PROJECT_ID, settings.NOTIFICATION_STATUS_UPDATE_TOPIC_ID
    )
    status_update_payload = {
        "original_reminder_id": original_reminder_id,
        "user_id": user_id,
        "reminder_mode": reminder_mode,
        "final_notification_status": final_status,  # This is the status of the notification dispatch itself
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "error_detail": error_detail,
    }
    message_json = json.dumps(status_update_payload)
    message_bytes = message_json.encode("utf-8")

    try:
        publish_future = publisher.publish(topic_path, message_bytes)
        publish_future.result(timeout=10)  # Wait for publish with a timeout
        logger.info(
            f"Successfully published status update for reminder {original_reminder_id} to {topic_path}: {final_status}"
        )
    except Exception as e:
        logger.error(
            f"Failed to publish status update for reminder {original_reminder_id} to {topic_path}: {e}",
            exc_info=True,
        )


async def process_single_notification(payload: PubSubMessageData, db: firestore.Client):
    """
    Core logic to process a single notification request.
    This is called by the Pub/Sub push endpoint handlers.
    """
    log_id = None  # Initialize log_id
    final_send_status_msg = "unknown_error"
    error_for_status_update = None
    send_successful = False

    try:
        # 1. Initial Log: "processing"
        log_id = await _log_notification_attempt(db, payload, status="processing")

        # 2. Get appropriate sender
        sender: INotificationSender = get_sender(payload.reminder_mode)
        contact_for_log = (
            payload.contact_email
            if payload.reminder_mode == "email"
            else payload.contact_phone
        )

        # 3. (Mock) Send the notification
        send_successful, final_send_status_msg = await sender.send(payload)

        # 4. Update Log: "sent_mock_..." or "failed_..."
        await _log_notification_attempt(
            db,
            payload,
            status=final_send_status_msg,
            log_id_override=log_id,
            contact_target=contact_for_log,
        )

    except ValueError as e:  # E.g. from get_sender or payload issues
        logger.error(
            f"ValueError processing notification for reminder {payload.original_reminder_id}: {e}",
            exc_info=True,
        )
        final_send_status_msg = "failed_invalid_request_data"
        error_for_status_update = str(e)
        if log_id:  # If initial log entry was created
            await _log_notification_attempt(
                db,
                payload,
                status=final_send_status_msg,
                log_id_override=log_id,
                error_message=str(e),
            )
        # If log_id is None, it means error happened before initial log, so we can't update it.
    except Exception as e:
        logger.error(
            f"Unexpected error processing notification for reminder {payload.original_reminder_id}: {e}",
            exc_info=True,
        )
        final_send_status_msg = "failed_internal_service_error"
        error_for_status_update = str(e)
        if log_id:
            await _log_notification_attempt(
                db,
                payload,
                status=final_send_status_msg,
                log_id_override=log_id,
                error_message=str(e),
            )
    finally:
        # 5. Publish final status to status update topic (regardless of success/failure of send)
        await _publish_status_update(
            original_reminder_id=payload.original_reminder_id,
            final_status=final_send_status_msg,  # The status of the send attempt
            user_id=payload.user_id,
            reminder_mode=payload.reminder_mode,
            error_detail=error_for_status_update,
        )
        if log_id:  # Mark that the final status has been published
            log_doc_ref = db.collection(settings.NOTIFICATION_LOG_COLLECTION).document(
                log_id
            )
            log_doc_ref.update(
                {
                    "final_status_published_at": datetime.datetime.now(
                        datetime.timezone.utc
                    )
                }
            )


# --- Pub/Sub Push Endpoints ---
# These endpoints will be targeted by Pub/Sub push subscriptions.
# The Pub/Sub message is in the request body.


@app.post(
    "/notifications/handle/email", status_code=204
)  # 204 No Content is good for Pub/Sub ack
async def handle_email_notification_push(
    request_body: PubSubMessage = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Handles email notification requests pushed from Pub/Sub."""
    logger.info(
        f"Received Pub/Sub push for EMAIL on subscription: {request_body.subscription}"
    )
    db = get_firestore_client()
    try:
        payload = request_body.get_payload()
        if payload.reminder_mode != "email":
            logger.error(
                f"Mismatched mode: Endpoint for 'email', but payload mode is '{payload.reminder_mode}'. Discarding."
            )
            # Ack the message to prevent redelivery for this specific error type
            return  # Implicit 204
    except ValueError as e:
        logger.error(
            f"Failed to decode Pub/Sub message data for email: {e}", exc_info=True
        )
        # Ack the message as it's likely unprocessable.
        # Could log a placeholder in NotificationLog if critical fields are extractable, or just log here.
        return  # Implicit 204

    # Process the notification in the background to quickly ack the Pub/Sub message
    background_tasks.add_task(process_single_notification, payload, db)
    logger.info(
        f"Email notification for reminder {payload.original_reminder_id} handed off to background task."
    )
    return  # FastAPI will return 204 by default for an empty response body


@app.post("/notifications/handle/phone-mock", status_code=204)
async def handle_phone_mock_notification_push(
    request_body: PubSubMessage = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Handles mock phone call notification requests pushed from Pub/Sub."""
    logger.info(
        f"Received Pub/Sub push for PHONE-MOCK on subscription: {request_body.subscription}"
    )
    db = get_firestore_client()
    try:
        payload = request_body.get_payload()
        if payload.reminder_mode != "phone_call_mock":
            logger.error(
                f"Mismatched mode: Endpoint for 'phone_call_mock', but payload mode is '{payload.reminder_mode}'. Discarding."
            )
            return
    except ValueError as e:
        logger.error(
            f"Failed to decode Pub/Sub message data for phone-mock: {e}", exc_info=True
        )
        return

    background_tasks.add_task(process_single_notification, payload, db)
    logger.info(
        f"Phone-mock notification for reminder {payload.original_reminder_id} handed off to background task."
    )
    return


# --- Root and Health Check ---
@app.get("/")
async def read_root():
    return {"message": "Welcome to the Fixture Scout AI - Notification Service"}


@app.get("/health")
async def health_check():
    db_ok = False
    pubsub_publisher_ok = bool(
        get_publisher_client()
    )  # Check if publisher was initialized
    try:
        get_firestore_client()
        db_ok = True
    except Exception:
        logger.warning("Health check: Firestore client not healthy.")

    if db_ok and pubsub_publisher_ok:
        return {
            "status": "ok",
            "firestore_healthy": True,
            "pubsub_publisher_initialized": True,
        }
    else:
        return {
            "status": "degraded",
            "firestore_healthy": db_ok,
            "pubsub_publisher_initialized": pubsub_publisher_ok,
            "detail": "One or more components are not healthy.",
        }
