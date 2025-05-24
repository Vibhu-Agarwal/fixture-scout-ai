# user_management_service/app/services/reminder_query_service.py
import logging
import datetime
from typing import List, Dict, Any

from google.cloud import firestore
from pydantic import ValidationError

from ..config import settings
from ..models import (
    UserReminderItem,
    FixtureInfo,
    ReminderDocInternal,
    FixtureDocInternal,
)

logger = logging.getLogger(__name__)


class ReminderQueryError(Exception):
    pass


def _get_next_reminder_trigger_details(
    reminder_triggers: List[Dict[str, Any]], kickoff_time: datetime.datetime
) -> tuple[datetime.datetime | None, str | None, str | None]:
    """
    Finds the next upcoming reminder trigger from the list.
    Returns (actual_reminder_time, mode, message) for the next trigger, or (None, None, None) if none are upcoming.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    next_trigger_time = None
    next_trigger_mode = None
    next_trigger_message = None

    for trigger in reminder_triggers:
        try:
            offset_minutes = int(
                trigger.get("reminder_offset_minutes_before_kickoff", 0)
            )
            actual_time = kickoff_time - datetime.timedelta(minutes=offset_minutes)

            if actual_time > now_utc:  # Only consider future triggers
                if next_trigger_time is None or actual_time < next_trigger_time:
                    next_trigger_time = actual_time
                    next_trigger_mode = trigger.get("reminder_mode")
                    next_trigger_message = trigger.get("custom_message")
        except (TypeError, ValueError) as e:
            logger.warning(
                f"Skipping invalid reminder trigger due to parsing error: {trigger}, Error: {e}"
            )
            continue

    return next_trigger_time, next_trigger_mode, next_trigger_message


async def get_user_future_reminders(
    db: firestore.Client, user_id: str
) -> List[UserReminderItem]:
    logger.info(f"Fetching future reminders for user_id: {user_id}")
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # Step 1: Fetch future, actionable reminders for the user
    # We query for reminders whose actual_reminder_time_utc is in the future
    # and whose status indicates they are still relevant to be shown as "upcoming".
    relevant_statuses = [
        "pending",
        "queued_for_notification",
        "triggered",
    ]  # Define what's "upcoming"

    reminders_query = (
        db.collection(settings.REMINDERS_COLLECTION)
        .where("user_id", "==", user_id)
        .where(
            "actual_reminder_time_utc", ">=", now_utc
        )  # Key filter: only future actual reminders
        .where("status", "in", relevant_statuses)  # Filter by relevant statuses
        .order_by(
            "actual_reminder_time_utc"
        )  # Order by when the reminder will actually occur
        .stream()
    )

    user_reminders_list: List[UserReminderItem] = []
    fixture_ids_to_fetch = set()
    # Store validated ReminderDocInternal objects directly
    processed_reminders_data: List[ReminderDocInternal] = []

    for reminder_snap in reminders_query:
        try:
            reminder_data = reminder_snap.to_dict()
            internal_reminder = ReminderDocInternal(**reminder_data)

            processed_reminders_data.append(internal_reminder)
            fixture_ids_to_fetch.add(internal_reminder.fixture_id)

        except ValidationError as e:
            logger.error(
                f"Invalid data for reminder {reminder_snap.id} for user {user_id}: {e}",
                exc_info=True,
            )
            continue
        except Exception as e:
            logger.error(
                f"Unexpected error processing reminder {reminder_snap.id}: {e}",
                exc_info=True,
            )
            continue

    if not processed_reminders_data:
        logger.info(f"No future, processable reminders found for user {user_id}.")
        return []

    # Step 2: Fetch fixture details (this part remains similar)
    fixtures_map: Dict[str, FixtureInfo] = {}
    if fixture_ids_to_fetch:
        fixture_id_list = list(fixture_ids_to_fetch)
        MAX_IN_VALUES = 30
        for i in range(0, len(fixture_id_list), MAX_IN_VALUES):
            batch_ids = fixture_id_list[i : i + MAX_IN_VALUES]
            fixtures_docs_query = (
                db.collection(settings.FIXTURES_COLLECTION)
                .where("fixture_id", "in", batch_ids)
                .stream()
            )
            for fixture_snap in fixtures_docs_query:
                try:
                    fixture_data = fixture_snap.to_dict()
                    if "fixture_id" not in fixture_data:
                        logger.warning(
                            f"Fixture document {fixture_snap.id} missing 'fixture_id' field."
                        )
                        continue
                    internal_fixture = FixtureDocInternal(**fixture_data)
                    fixtures_map[internal_fixture.fixture_id] = FixtureInfo(
                        fixture_id=internal_fixture.fixture_id,
                        home_team_name=internal_fixture.home_team.get("name", "N/A"),
                        away_team_name=internal_fixture.away_team.get("name", "N/A"),
                        league_name=internal_fixture.league_name,
                        match_datetime_utc=internal_fixture.match_datetime_utc,
                        stage=internal_fixture.stage,
                    )
                except ValidationError as e:
                    logger.error(
                        f"Invalid data for fixture {fixture_snap.id}: {e}",
                        exc_info=True,
                    )
                except Exception as e:  # Catch-all for unexpected errors
                    logger.error(
                        f"Unexpected error processing fixture {fixture_snap.id}: {e}",
                        exc_info=True,
                    )

    # Step 3: Combine reminder data with fixture data
    for (
        reminder_doc
    ) in (
        processed_reminders_data
    ):  # Iterate over the validated ReminderDocInternal objects
        fixture_detail = fixtures_map.get(reminder_doc.fixture_id)
        if not fixture_detail:
            logger.warning(
                f"Fixture details not found for fixture_id: {reminder_doc.fixture_id} (reminder: {reminder_doc.reminder_id}). Skipping this reminder."
            )
            continue

        # Since each reminder_doc is now a specific trigger, its fields are directly used
        user_reminders_list.append(
            UserReminderItem(
                reminder_id=reminder_doc.reminder_id,
                fixture_details=fixture_detail,
                importance_score=reminder_doc.importance_score,  # This was likely the match importance
                custom_message=reminder_doc.custom_message,  # Message for THIS specific trigger
                reminder_mode=reminder_doc.reminder_mode,  # Mode of THIS specific trigger
                actual_reminder_time_utc=reminder_doc.actual_reminder_time_utc,  # Time of THIS trigger
                current_status=reminder_doc.status,  # Status of THIS trigger processing
                kickoff_time_utc=reminder_doc.kickoff_time_utc,
            )
        )

    # The list is already sorted by actual_reminder_time_utc from the Firestore query
    # If you needed to re-sort for any reason, you could do it here.

    logger.info(
        f"Returning {len(user_reminders_list)} future reminders for user {user_id}."
    )
    return user_reminders_list
