# reminder_scheduler_service/app/main.py
import logging
import datetime
import json
import os
from typing import Dict, List
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from contextlib import asynccontextmanager
from google.cloud import pubsub_v1 # Import Pub/Sub client
from google.cloud.pubsub_v1.publisher.exceptions import MessageTooLargeError
from google.api_core.exceptions import NotFound as PubSubTopicNotFound
from google.api_core.exceptions import AlreadyExists, NotFound

from .utils.logging_config import setup_logging
setup_logging()

from .config import settings
from .firestore_client import get_firestore_client
from google.cloud import firestore
from .models import ReminderDocFromDB, UserDocFromDB

logger = logging.getLogger(__name__)

# Global Pub/Sub Publisher client, initialized during lifespan
publisher_client: pubsub_v1.PublisherClient | None = None

async def _ensure_pubsub_topic_exists(publisher: pubsub_v1.PublisherClient, project_id: str, topic_id: str):
    """Ensures a Pub/Sub topic exists, creating it if necessary."""
    topic_path = publisher.topic_path(project_id, topic_id)
    try:
        publisher.get_topic(topic=topic_path) # Changed from request= to topic=
        logger.info(f"Pub/Sub topic '{topic_path}' already exists.")
    except NotFound:
        logger.info(f"Pub/Sub topic '{topic_path}' not found. Creating it...")
        try:
            publisher.create_topic(name=topic_path) # Changed from request= to name=
            logger.info(f"Pub/Sub topic '{topic_path}' created successfully.")
        except AlreadyExists:
            logger.info(f"Pub/Sub topic '{topic_path}' was created by another process concurrently.")
        except Exception as e_create:
            logger.error(f"Failed to create Pub/Sub topic '{topic_path}': {e_create}", exc_info=True)
            raise # Re-raise to indicate a startup problem
    except Exception as e_get:
        logger.error(f"Failed to check existence of Pub/Sub topic '{topic_path}': {e_get}", exc_info=True)
        raise # Re-raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    global publisher_client
    logger.info("Reminder Scheduler Service starting up...")
    try:
        get_firestore_client()
        
        # Determine project_id for Pub/Sub operations
        project_id_for_pubsub = settings.GCP_PROJECT_ID
        if os.getenv("PUBSUB_EMULATOR_HOST") and not project_id_for_pubsub:
            # If using emulator and no project_id set, you might use a default/dummy for topic creation
            # For this example, let's assume settings.GCP_PROJECT_ID should be set.
            # Or, if you know the emulator uses a specific default, use that.
            logger.warning("GCP_PROJECT_ID not set; Pub/Sub topic creation/check might behave unexpectedly with emulator without a project context.")
            # Fallback to a dummy project for emulator if absolutely necessary and client allows
            # project_id_for_pubsub = "your-dummy-emulator-project" 
        
        if not project_id_for_pubsub and not os.getenv("PUBSUB_EMULATOR_HOST"):
             logger.critical("GCP_PROJECT_ID is not set. Cannot initialize Pub/Sub topics for real environment.")
             raise ValueError("GCP_PROJECT_ID must be set for Pub/Sub operations outside the emulator.")

        publisher_client = pubsub_v1.PublisherClient()
        logger.info("Firestore client and Pub/Sub Publisher client initialized.")

        # Ensure topics exist (only if project_id_for_pubsub is available)
        if project_id_for_pubsub: # Proceed only if we have a project ID
            topics = [settings.EMAIL_NOTIFICATIONS_TOPIC_ID, settings.PHONE_MOCK_NOTIFICATIONS_TOPIC_ID]
            for topic in topics:
                await _ensure_pubsub_topic_exists(publisher_client, project_id_for_pubsub, topic)
        else:
            logger.warning("Skipping Pub/Sub topic existence check/creation as GCP_PROJECT_ID is not definitively set for non-emulator or emulator context.")


    except Exception as e:
        logger.critical(f"Failed to initialize clients or Pub/Sub topics on startup: {e}", exc_info=True)
        # Decide if app should exit or continue in a degraded state
    yield
    logger.info("Reminder Scheduler Service shutting down...")


app = FastAPI(
    title="Reminder Scheduler Service",
    description="Checks for due reminders, publishes them to Pub/Sub topics.",
    version="0.1.0",
    lifespan=lifespan
)

async def _publish_to_pubsub(topic_id: str, data: Dict) -> bool:
    """
    Publishes a message to the specified Pub/Sub topic.
    Returns True if publishing was successful, False otherwise.
    """
    if not publisher_client:
        logger.error("Pub/Sub Publisher client not initialized. Cannot publish message.")
        return False
    if not settings.GCP_PROJECT_ID and not os.getenv("PUBSUB_EMULATOR_HOST"):
        logger.error("GCP_PROJECT_ID is not set; cannot form full topic path for Pub/Sub.")
        # This check is a bit redundant if publisher_client init succeeded but good for safety
        return False

    # Construct the full topic path.
    # For the emulator, project_id in topic_path might not be strictly required if PUBSUB_EMULATOR_HOST is set,
    # as the client often infers or uses a default. However, for real GCP, it's essential.
    # The client library should handle the emulator case correctly if PUBSUB_EMULATOR_HOST is set.
    # We MUST provide a project_id to topic_path for non-emulator scenarios.
    project_id_for_path = settings.GCP_PROJECT_ID
    if os.getenv("PUBSUB_EMULATOR_HOST") and not project_id_for_path:
        # In emulator, if project_id is not set, use a placeholder if client requires it.
        # Often, for emulator, just topic_id is enough or it uses a default project from gcloud.
        # Let's assume the client library handles this. If issues arise, explicitly pass a placeholder project.
        logger.warning("GCP_PROJECT_ID not set, relying on Pub/Sub emulator's default project handling for topic path.")
        # If Pub/Sub client requires project_id for topic_path even with emulator,
        # you might need to pass a dummy one like "local-project"
        # For now, assume `settings.GCP_PROJECT_ID` is set or emulator handles it.
        # The most robust way for the client to form the path:
        if not project_id_for_path: # If still none after above logic
            logger.error("Cannot determine project ID for Pub/Sub topic path construction.")
            return False

    topic_path = publisher_client.topic_path(project_id_for_path, topic_id) # type: ignore
    message_json = json.dumps(data)
    message_bytes = message_json.encode("utf-8")

    logger.debug(f"Publishing to Pub/Sub topic: {topic_path}, Data: {data}")
    try:
        publish_future = publisher_client.publish(topic_path, message_bytes)
        publish_future.result()  # Wait for publish to complete / raise exception on failure
        logger.info(f"Successfully published message for reminder_id {data.get('original_reminder_id')} to topic {topic_id}.")
        return True
    except MessageTooLargeError:
        logger.error(f"Message for reminder {data.get('original_reminder_id')} is too large for Pub/Sub topic {topic_id}.", exc_info=True)
        return False
    except PubSubTopicNotFound:
        logger.error(f"Pub/Sub topic {topic_path} not found.", exc_info=True)
        # This is a critical configuration error.
        return False
    except Exception as e:
        logger.error(f"Failed to publish message for reminder {data.get('original_reminder_id')} to topic {topic_id}: {e}", exc_info=True)
        return False


async def _update_reminder_status_in_firestore(db: firestore.Client, reminder_id: str, new_status: str, details: Dict | None = None):
    """Helper to update reminder status and updated_at timestamp in Firestore."""
    try:
        reminder_update_ref = db.collection(settings.REMINDERS_COLLECTION).document(reminder_id)
        update_data = {"status": new_status, "updated_at": datetime.datetime.now(datetime.timezone.utc)}
        if details:
            update_data.update(details)
        reminder_update_ref.update(update_data)
        logger.info(f"Updated status of reminder {reminder_id} to '{new_status}'.")
    except Exception as e:
        logger.error(f"Failed to update status for reminder {reminder_id} to '{new_status}': {e}", exc_info=True)


@app.post("/scheduler/check-and-dispatch-reminders", status_code=200)
async def check_and_dispatch_reminders_endpoint():
    """
    Checks for pending reminders that are due and publishes them to Pub/Sub topics.
    """
    logger.info("Scheduler: Checking for due reminders to publish...")
    db = get_firestore_client()
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    total_due_reminders = 0
    successfully_queued = 0
    failed_to_queue = 0
    skipped_due_to_data_issues = 0

    try:
        due_reminders_query = (db.collection(settings.REMINDERS_COLLECTION)\
            .where("status", "==", "pending")\
            .where("actual_reminder_time_utc", "<=", now_utc)\
            .limit(200)
            .stream())

        reminders_to_process: List[ReminderDocFromDB] = []
        for reminder_snap in due_reminders_query:
            total_due_reminders += 1
            try:
                reminder_data = reminder_snap.to_dict()
                reminder = ReminderDocFromDB(**reminder_data)
                reminders_to_process.append(reminder)
            except ValidationError as e:
                logger.error(f"Scheduler: Invalid reminder data for doc {reminder_snap.id}: {e}. Skipping.", exc_info=True)
                await _update_reminder_status_in_firestore(db, reminder_snap.id, "error_validation", {"error_detail": str(e)[:500]})
                skipped_due_to_data_issues += 1
            except Exception as e:
                logger.error(f"Scheduler: Unexpected error processing reminder doc {reminder_snap.id}: {e}. Skipping.", exc_info=True)
                await _update_reminder_status_in_firestore(db, reminder_snap.id, "error_processing", {"error_detail": str(e)[:500]})
                skipped_due_to_data_issues += 1
        
        if not reminders_to_process:
            logger.info("Scheduler: No due 'pending' reminders found matching criteria or after filtering.")
            return {
                "message": "No due reminders found to process.",
                "total_due_reminders_queried": total_due_reminders,
                "successfully_queued": 0,
                "failed_to_queue": 0,
                "skipped_due_to_data_issues": skipped_due_to_data_issues
            }

        logger.info(f"Scheduler: Found {len(reminders_to_process)} valid due reminders to process out of {total_due_reminders} queried.")

        for reminder in reminders_to_process:
            logger.info(f"Scheduler: Processing reminder: {reminder.reminder_id} for user {reminder.user_id} mode: {reminder.reminder_mode}")

            user_doc_ref = db.collection(settings.USERS_COLLECTION).document(reminder.user_id)
            user_snap = user_doc_ref.get()

            if not user_snap.exists:
                logger.error(f"Scheduler: User {reminder.user_id} not found for reminder {reminder.reminder_id}.")
                await _update_reminder_status_in_firestore(db, reminder.reminder_id, "failed_user_not_found")
                failed_to_queue += 1
                continue
            
            try:
                user_contact = UserDocFromDB(**user_snap.to_dict())
            except ValidationError as e:
                logger.error(f"Scheduler: Invalid user data for user {reminder.user_id} (reminder {reminder.reminder_id}): {e}.", exc_info=True)
                await _update_reminder_status_in_firestore(db, reminder.reminder_id, "failed_invalid_user_data", {"error_detail": str(e)[:500]})
                failed_to_queue += 1
                continue

            # Prepare Pub/Sub message data
            notification_request_data = {
                "original_reminder_id": reminder.reminder_id,
                "user_id": reminder.user_id,
                "fixture_id": reminder.fixture_id,
                "contact_email": str(user_contact.email) if user_contact.email else None,
                "contact_phone": user_contact.phone_number,
                "message_content": reminder.custom_message,
                "reminder_mode": reminder.reminder_mode,
                "kickoff_time_utc": reminder.kickoff_time_utc.isoformat(), # For context in notification service if needed
            }

            # Determine target Pub/Sub topic
            target_topic_id = None
            if reminder.reminder_mode == "email":
                target_topic_id = settings.EMAIL_NOTIFICATIONS_TOPIC_ID
            elif reminder.reminder_mode == "phone_call_mock":
                target_topic_id = settings.PHONE_MOCK_NOTIFICATIONS_TOPIC_ID
            # Add more modes/topics as needed

            if not target_topic_id:
                logger.error(f"Scheduler: Unknown reminder_mode '{reminder.reminder_mode}' for reminder {reminder.reminder_id}. Cannot determine Pub/Sub topic.")
                await _update_reminder_status_in_firestore(db, reminder.reminder_id, "failed_unknown_mode")
                failed_to_queue += 1
                continue

            # Publish to Pub/Sub
            publish_successful = await _publish_to_pubsub(target_topic_id, notification_request_data)

            if publish_successful:
                await _update_reminder_status_in_firestore(db, reminder.reminder_id, "queued_for_notification", {"published_to_topic": target_topic_id})
                successfully_queued += 1
            else:
                # _publish_to_pubsub already logs errors
                await _update_reminder_status_in_firestore(db, reminder.reminder_id, "failed_queueing")
                failed_to_queue += 1
        
        summary_message = (
            f"Scheduler: Publish check complete. "
            f"Successfully Queued: {successfully_queued}. "
            f"Failed to Queue: {failed_to_queue}. "
            f"Skipped Data Issues: {skipped_due_to_data_issues}. "
            f"Total Queried Due: {total_due_reminders}."
        )
        logger.info(summary_message)
        return {
            "message": summary_message,
            "successfully_queued": successfully_queued,
            "failed_to_queue": failed_to_queue,
            "skipped_due_to_data_issues": skipped_due_to_data_issues,
            "total_due_reminders_queried": total_due_reminders,
            "valid_reminders_processed": len(reminders_to_process)
        }

    except Exception as e:
        logger.critical(f"Scheduler: Critical error during reminder publish check: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Reminder publish check failed due to an internal error: {str(e)}")


@app.get("/")
async def read_root():
    return {"message": "Welcome to the Fixture Scout AI - Reminder Scheduler Service (Pub/Sub Enabled)"}

# Health check can remain similar, perhaps add a check for publisher_client initialization
@app.get("/health")
async def health_check():
    db_ok = False
    pubsub_ok = bool(publisher_client)
    try:
        get_firestore_client()
        db_ok = True
    except Exception:
        logger.warning("Health check: Firestore client not healthy or accessible.")
    
    if db_ok and pubsub_ok:
        return {"status": "ok", "firestore_healthy": True, "pubsub_publisher_initialized": True}
    else:
        return {
            "status": "degraded",
            "firestore_healthy": db_ok,
            "pubsub_publisher_initialized": pubsub_ok,
            "detail": "One or more components are not healthy."
        }