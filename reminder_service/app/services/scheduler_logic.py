# reminder_scheduler_service/app/services/scheduler_logic.py
import logging
import datetime
from typing import Dict, List

from pydantic import ValidationError
from google.cloud import firestore
from google.cloud import pubsub_v1

from ..config import settings
from ..models import ReminderDocFromDB, UserDocFromDB
from ..pubsub_utils import publish_to_pubsub

logger = logging.getLogger(__name__)


async def update_reminder_status_in_firestore(
    db: firestore.Client, reminder_id: str, new_status: str, details: Dict | None = None
):
    """Helper to update reminder status and updated_at timestamp in Firestore."""
    try:
        reminder_update_ref = db.collection(settings.REMINDERS_COLLECTION).document(
            reminder_id
        )
        update_data = {
            "status": new_status,
            "updated_at": datetime.datetime.now(datetime.timezone.utc),
        }
        if details:
            update_data.update(details)
        reminder_update_ref.update(update_data)
        logger.info(f"Updated status of reminder {reminder_id} to '{new_status}'.")
    except Exception as e:
        logger.error(
            f"Failed to update status for reminder {reminder_id} to '{new_status}': {e}",
            exc_info=True,
        )


async def fetch_and_process_due_reminders(
    db: firestore.Client, publisher: pubsub_v1.PublisherClient
) -> Dict:
    """
    Fetches due reminders and processes them by publishing to Pub/Sub.
    Returns a summary dictionary of the operation.
    """
    logger.info("Scheduler Logic: Checking for due reminders to publish...")
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    total_due_reminders = 0
    successfully_queued = 0
    failed_to_queue = 0
    skipped_due_to_data_issues = 0

    # This part remains largely the same, but calls will be to local/imported functions
    due_reminders_query = (
        db.collection(settings.REMINDERS_COLLECTION)
        .where("status", "==", "pending")
        # .where("actual_reminder_time_utc", "<=", now_utc)
        .limit(200)  # Keep the limit for safety
        .stream()
    )

    reminders_to_process: List[ReminderDocFromDB] = []
    for reminder_snap in due_reminders_query:
        total_due_reminders += 1
        try:
            reminder_data = reminder_snap.to_dict()
            reminder = ReminderDocFromDB(**reminder_data)
            reminders_to_process.append(reminder)
        except ValidationError as e:
            logger.error(
                f"Scheduler Logic: Invalid reminder data for doc {reminder_snap.id}: {e}. Skipping.",
                exc_info=True,
            )
            await update_reminder_status_in_firestore(
                db, reminder_snap.id, "error_validation", {"error_detail": str(e)[:500]}
            )
            skipped_due_to_data_issues += 1
        except Exception as e:
            logger.error(
                f"Scheduler Logic: Unexpected error processing reminder doc {reminder_snap.id}: {e}. Skipping.",
                exc_info=True,
            )
            await update_reminder_status_in_firestore(
                db, reminder_snap.id, "error_processing", {"error_detail": str(e)[:500]}
            )
            skipped_due_to_data_issues += 1

    if not reminders_to_process:
        logger.info(
            "Scheduler Logic: No due 'pending' reminders found matching criteria or after filtering."
        )
        return {
            "message": "No due reminders found to process.",
            "total_due_reminders_queried": total_due_reminders,
            "successfully_queued": 0,
            "failed_to_queue": 0,
            "skipped_due_to_data_issues": skipped_due_to_data_issues,
        }

    logger.info(
        f"Scheduler Logic: Found {len(reminders_to_process)} valid due reminders to process out of {total_due_reminders} queried."
    )

    project_id_for_pubsub = settings.GCP_PROJECT_ID  # This should be set from config

    for reminder in reminders_to_process:
        logger.info(
            f"Scheduler Logic: Processing reminder: {reminder.reminder_id} for user {reminder.user_id} mode: {reminder.reminder_mode}"
        )

        user_doc_ref = db.collection(settings.USERS_COLLECTION).document(
            reminder.user_id
        )
        user_snap = user_doc_ref.get()  # Firestore client calls are synchronous

        if not user_snap.exists:
            logger.error(
                f"Scheduler Logic: User {reminder.user_id} not found for reminder {reminder.reminder_id}."
            )
            await update_reminder_status_in_firestore(
                db, reminder.reminder_id, "failed_user_not_found"
            )
            failed_to_queue += 1
            continue

        try:
            user_contact = UserDocFromDB(**user_snap.to_dict())
        except ValidationError as e:
            logger.error(
                f"Scheduler Logic: Invalid user data for user {reminder.user_id} (reminder {reminder.reminder_id}): {e}.",
                exc_info=True,
            )
            await update_reminder_status_in_firestore(
                db,
                reminder.reminder_id,
                "failed_invalid_user_data",
                {"error_detail": str(e)[:500]},
            )
            failed_to_queue += 1
            continue

        notification_request_data = {
            "original_reminder_id": reminder.reminder_id,
            "user_id": reminder.user_id,
            "fixture_id": reminder.fixture_id,
            "contact_email": str(user_contact.email) if user_contact.email else None,
            "contact_phone": user_contact.phone_number,
            "message_content": reminder.custom_message,
            "reminder_mode": reminder.reminder_mode,
            "kickoff_time_utc": reminder.kickoff_time_utc.isoformat(),
        }

        target_topic_id = None
        if reminder.reminder_mode == "email":
            target_topic_id = settings.EMAIL_NOTIFICATIONS_TOPIC_ID
        elif reminder.reminder_mode == "phone_call_mock":
            target_topic_id = settings.PHONE_MOCK_NOTIFICATIONS_TOPIC_ID

        if not target_topic_id:
            logger.error(
                f"Scheduler Logic: Unknown reminder_mode '{reminder.reminder_mode}' for reminder {reminder.reminder_id}."
            )
            await update_reminder_status_in_firestore(
                db, reminder.reminder_id, "failed_unknown_mode"
            )
            failed_to_queue += 1
            continue

        if (
            not project_id_for_pubsub
        ):  # Should have been caught earlier, but as a safeguard
            logger.error(
                "Scheduler Logic: GCP_PROJECT_ID not configured. Cannot publish."
            )
            await update_reminder_status_in_firestore(
                db, reminder.reminder_id, "failed_config_error"
            )
            failed_to_queue += 1
            continue

        publish_successful = await publish_to_pubsub(
            publisher, project_id_for_pubsub, target_topic_id, notification_request_data
        )

        if publish_successful:
            await update_reminder_status_in_firestore(
                db,
                reminder.reminder_id,
                "queued_for_notification",
                {"published_to_topic": target_topic_id},
            )
            successfully_queued += 1
        else:
            await update_reminder_status_in_firestore(
                db, reminder.reminder_id, "failed_queueing"
            )
            failed_to_queue += 1

    summary_message = (
        f"Scheduler Logic: Publish check complete. "
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
        "valid_reminders_processed": len(reminders_to_process),
    }
