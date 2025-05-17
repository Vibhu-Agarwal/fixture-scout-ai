# reminder_service/app/services/status_updater_logic.py
import logging
import datetime
from typing import Dict

from google.cloud import firestore

from ..config import settings
from ..models import NotificationStatusUpdatePayload

logger = logging.getLogger(__name__)


async def process_reminder_status_update(
    db: firestore.Client, payload: NotificationStatusUpdatePayload
) -> bool:
    """
    Processes a notification status update: updates the original Reminder document.
    Returns True if successfully processed, False otherwise.
    """
    logger.info(
        f"StatusUpdater: Processing status update for original_reminder_id: {payload.original_reminder_id}, new_status: {payload.final_notification_status}"
    )

    reminder_doc_ref = db.collection(settings.REMINDERS_COLLECTION).document(
        payload.original_reminder_id
    )

    try:
        # Determine the new status for the Reminders collection.
        # This might involve mapping from `final_notification_status`.
        # For now, let's use a simple mapping.
        # A more sophisticated system might have more granular statuses.
        new_reminder_collection_status = "unknown"
        if (
            "sent_mock" in payload.final_notification_status
            or "delivered" in payload.final_notification_status
        ):
            new_reminder_collection_status = (
                "sent"  # Final success state for the reminder
            )
        elif "failed" in payload.final_notification_status:
            new_reminder_collection_status = f"failed_notification_{payload.final_notification_status.split('failed_')[-1]}"
            if payload.error_detail:
                new_reminder_collection_status = (
                    f"failed_notification_delivery"  # General category
                )
        else:
            logger.warning(
                f"StatusUpdater: Unhandled final_notification_status '{payload.final_notification_status}' for reminder {payload.original_reminder_id}. Defaulting status."
            )
            new_reminder_collection_status = (
                f"status_update_{payload.final_notification_status}"  # Store as is
            )

        update_data = {
            "status": new_reminder_collection_status,
            "updated_at": datetime.datetime.now(datetime.timezone.utc),
            "last_notification_outcome": payload.final_notification_status,  # Store the direct outcome
            "last_notification_outcome_at_utc": datetime.datetime.fromisoformat(
                payload.timestamp_utc
            ),
        }
        if payload.error_detail:
            update_data["last_notification_error_detail"] = payload.error_detail[
                :500
            ]  # Truncate

        reminder_doc_ref.update(update_data)
        logger.info(
            f"StatusUpdater: Successfully updated reminder {payload.original_reminder_id} to status '{new_reminder_collection_status}'."
        )
        return True

    except Exception as e:
        logger.error(
            f"StatusUpdater: Failed to update reminder {payload.original_reminder_id} in Firestore: {e}",
            exc_info=True,
        )
        return False
