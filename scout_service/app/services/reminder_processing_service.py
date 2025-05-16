# scout_service/app/services/reminder_processing_service.py
import logging
import datetime
import uuid
import json
from typing import List, Dict, Tuple

from google.cloud import (
    firestore,
)  # For type hinting if needed, db interaction via client
from vertexai.generative_models import (  # For type hinting
    GenerativeModel,
    GenerationConfig,
    HarmCategory,
    HarmBlockThreshold,
)

from ..config import settings  # Relative imports for modules within the 'app' package
from ..firestore_client import get_firestore_client
from ..vertex_ai_client import get_vertex_ai_gemini_client
from ..llm_prompts import construct_gemini_scout_prompt
from ..models import (
    FixtureForLLM,
    LLMSelectedFixtureResponse,
    FixtureDoc,  # Representing data structure from Firestore
)

logger = logging.getLogger(__name__)


class ReminderProcessingError(Exception):
    """Custom exception for errors during reminder processing."""

    pass


class LLMResponseError(ReminderProcessingError):
    """Custom exception for issues with LLM response."""

    pass


async def process_fixtures_for_user(user_id: str) -> Dict:
    """
    Processes upcoming fixtures for a given user:
    1. Fetches user preferences.
    2. Fetches upcoming fixtures.
    3. Calls LLM (Gemini via Vertex AI) to select matches and define reminders.
    4. Stores generated reminders in Firestore.
    Returns a summary dictionary of the operation.
    """
    db = get_firestore_client()
    gemini_model = get_vertex_ai_gemini_client()

    # 1. Fetch user's preference
    optimized_llm_prompt_text, user_exists = _fetch_user_preference(db, user_id)
    if not user_exists:
        raise ReminderProcessingError(
            f"User with ID {user_id} not found or preferences missing."
        )
    if not optimized_llm_prompt_text:
        raise ReminderProcessingError(
            f"Optimized LLM prompt not set for user {user_id}."
        )

    # 2. Fetch upcoming fixtures
    upcoming_fixtures_for_llm, original_fixtures_map = _fetch_upcoming_fixtures(db)
    if not upcoming_fixtures_for_llm:
        logger.info(f"No upcoming fixtures found to process for user {user_id}.")
        return {
            "message": f"No upcoming fixtures found to process for user {user_id}.",
            "user_id": user_id,
            "fixtures_analyzed_count": 0,
            "matches_selected_by_llm": 0,
            "reminders_created": 0,
        }

    # 3. Construct the prompt and call LLM
    full_llm_prompt = construct_gemini_scout_prompt(
        optimized_llm_prompt_text, upcoming_fixtures_for_llm
    )
    logger.debug(
        f"Constructed LLM prompt for user {user_id} (first 500 chars): {full_llm_prompt[:500]}..."
    )

    llm_response_raw_text, selected_matches_from_llm = _call_llm_and_parse_response(
        gemini_model, full_llm_prompt, user_id
    )

    # 4. Store reminders
    reminders_created_count = 0
    if selected_matches_from_llm:
        _clear_old_pending_reminders(
            db, user_id, [f.fixture_id for f in upcoming_fixtures_for_llm]
        )
        reminders_created_count = _store_new_reminders(
            db,
            user_id,
            selected_matches_from_llm,
            original_fixtures_map,
            full_llm_prompt,
            llm_response_raw_text,
        )
        logger.info(
            f"Successfully created {reminders_created_count} reminders for user {user_id}."
        )
    else:
        logger.info(
            f"No matches selected by LLM for user {user_id}. No new reminders created."
        )

    return {
        "message": f"Scout processing complete for user {user_id} via Vertex AI.",
        "user_id": user_id,
        "fixtures_analyzed_count": len(upcoming_fixtures_for_llm),
        "matches_selected_by_llm": len(selected_matches_from_llm),
        "reminders_created": reminders_created_count,
        "raw_llm_output_sample": f"{llm_response_raw_text[:200]}...",
    }


def _fetch_user_preference(
    db: firestore.Client, user_id: str
) -> Tuple[str | None, bool]:
    """Fetches the optimized LLM prompt for the user."""
    preference_doc_ref = db.collection(settings.USER_PREFERENCES_COLLECTION).document(
        user_id
    )
    preference_doc = preference_doc_ref.get()

    if not preference_doc.exists:
        logger.warning(f"Preferences for user ID {user_id} not found.")
        return None, False

    user_preferences = preference_doc.to_dict()
    optimized_llm_prompt = user_preferences.get("optimized_llm_prompt")
    logger.debug(
        f"User {user_id} optimized prompt fetched: {optimized_llm_prompt[:100] if optimized_llm_prompt else 'None'}..."
    )
    return optimized_llm_prompt, True


def _fetch_upcoming_fixtures(
    db: firestore.Client,
) -> Tuple[List[FixtureForLLM], Dict[str, Dict]]:
    """Fetches upcoming fixtures from Firestore and prepares them for the LLM."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    future_cutoff_utc = now_utc + datetime.timedelta(
        days=settings.FIXTURE_LOOKOUT_WINDOW_DAYS
    )
    logger.info(
        f"Fetching fixtures between {now_utc.isoformat()} and {future_cutoff_utc.isoformat()}"
    )

    fixtures_query = (
        db.collection(settings.FIXTURES_COLLECTION)
        .where("match_datetime_utc", ">=", now_utc)
        .where("match_datetime_utc", "<=", future_cutoff_utc)
        .order_by("match_datetime_utc")
        .stream()
    )

    upcoming_fixtures_for_llm: List[FixtureForLLM] = []
    original_fixtures_map: Dict[str, Dict] = (
        {}
    )  # Using Dict to represent FixtureDoc like structure

    for fixture_snap in fixtures_query:
        try:
            # Attempt to parse with Pydantic for validation, though Firestore returns dict
            fixture_data_dict = fixture_snap.to_dict()
            # fixture_doc = FixtureDoc(**fixture_data_dict) # Optional: Validate against Pydantic model
            original_fixtures_map[fixture_data_dict["fixture_id"]] = fixture_data_dict

            match_dt_utc = fixture_data_dict.get("match_datetime_utc")
            match_datetime_utc_str = (
                match_dt_utc.isoformat()
                if isinstance(match_dt_utc, datetime.datetime)
                else str(match_dt_utc)
            )

            # Handle potentially missing nested fields gracefully
            home_team_name = fixture_data_dict.get("home_team", {}).get(
                "name", "Unknown Home"
            )
            away_team_name = fixture_data_dict.get("away_team", {}).get(
                "name", "Unknown Away"
            )
            league_name = fixture_data_dict.get("league_name", "Unknown League")

            upcoming_fixtures_for_llm.append(
                FixtureForLLM(
                    fixture_id=fixture_data_dict["fixture_id"],
                    home_team_name=home_team_name,
                    away_team_name=away_team_name,
                    league_name=league_name,
                    match_datetime_utc_str=match_datetime_utc_str,
                    stage=fixture_data_dict.get("stage"),
                    raw_metadata_blob=fixture_data_dict.get("raw_metadata_blob"),
                )
            )
        except Exception as e:
            logger.error(
                f"Error processing fixture {fixture_snap.id}: {e}", exc_info=True
            )
            continue  # Skip this fixture

    logger.info(
        f"Fetched {len(upcoming_fixtures_for_llm)} upcoming fixtures for LLM processing."
    )
    return upcoming_fixtures_for_llm, original_fixtures_map


def _call_llm_and_parse_response(
    gemini_model: GenerativeModel, full_llm_prompt: str, user_id: str
) -> Tuple[str, List[LLMSelectedFixtureResponse]]:
    """Calls the LLM and parses its JSON response."""
    try:
        logger.info(
            f"Sending prompt to Vertex AI Gemini for user {user_id} (model: {settings.GEMINI_MODEL_NAME_VERTEX})."
        )
        generation_config = GenerationConfig(
            temperature=0.2,
            max_output_tokens=8192,  # Increased slightly just in case of many fixtures
            # top_p=0.95,
            # top_k=40
        )
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

        response = gemini_model.generate_content(
            full_llm_prompt,
            generation_config=generation_config,
            safety_settings=safety_settings,
            stream=False,
        )

        llm_response_raw_text = ""
        if hasattr(response, "text") and response.text:
            llm_response_raw_text = response.text
        else:
            llm_response_raw_text = "[]"  # Default to empty array if no text
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                logger.warning(
                    f"Prompt for user {user_id} was blocked by Vertex AI. Reason: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}"
                )
                raise LLMResponseError(
                    f"Prompt blocked by Vertex AI: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}"
                )
            elif (
                not response.candidates
                or not hasattr(response.candidates[0], "content")
                or not response.candidates[0].content.parts
            ):
                logger.warning(
                    f"Vertex AI Gemini response for user {user_id} was empty or malformed (no content parts)."
                )
                # No specific error to raise here, will result in empty list of matches

        logger.info(
            f"Raw LLM response snippet for user {user_id}: {llm_response_raw_text[:300]}..."
        )
        logger.debug(
            f"Full raw LLM response for user {user_id}:\n{llm_response_raw_text}"
        )

        # Parse JSON
        cleaned_response_str = llm_response_raw_text.strip()
        if cleaned_response_str.startswith("```json"):
            cleaned_response_str = cleaned_response_str[7:]
        if cleaned_response_str.startswith("```"):
            cleaned_response_str = cleaned_response_str[3:]
        if cleaned_response_str.endswith("```"):
            cleaned_response_str = cleaned_response_str[:-3]
        cleaned_response_str = cleaned_response_str.strip()

        if not cleaned_response_str:
            logger.warning(f"LLM response was empty after cleaning for user {user_id}.")
            return llm_response_raw_text, []

        try:
            parsed_data = json.loads(cleaned_response_str)
            selected_matches = [
                LLMSelectedFixtureResponse(**item) for item in parsed_data
            ]
            return llm_response_raw_text, selected_matches
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse LLM JSON response for user {user_id}: {e}. Problematic JSON: '{cleaned_response_str}'",
                exc_info=True,
            )
            raise LLMResponseError(
                f"LLM returned invalid JSON. Raw: {llm_response_raw_text[:200]}..."
            )
        except Exception as e:  # Pydantic validation or other errors
            logger.error(
                f"Error validating LLM response items for user {user_id}: {e}",
                exc_info=True,
            )
            # Decide if to raise, or return partial results, or empty. For now, raise.
            raise LLMResponseError(
                f"Error validating LLM response structure. Error: {e}"
            )

    except Exception as e:
        logger.error(
            f"Exception during Vertex AI Gemini API call or parsing for user {user_id}: {str(e)}",
            exc_info=True,
        )
        # Propagate the error after logging
        if not isinstance(e, LLMResponseError):  # Avoid re-wrapping our custom error
            raise LLMResponseError(f"General error during LLM interaction: {str(e)}")
        else:
            raise e


def _clear_old_pending_reminders(
    db: firestore.Client, user_id: str, fixture_ids_in_llm_input: List[str]
):
    """Deletes old 'pending' reminders for the given user and fixture IDs."""
    if not fixture_ids_in_llm_input:
        return

    logger.info(
        f"Clearing old pending reminders for user {user_id} for {len(fixture_ids_in_llm_input)} fixtures."
    )
    existing_reminders_query = (
        db.collection(settings.REMINDERS_COLLECTION)
        .where("user_id", "==", user_id)
        .where("fixture_id", "in", fixture_ids_in_llm_input)
        .where("status", "==", "pending")
        .stream()
    )

    delete_batch = db.batch()
    deleted_old_count = 0
    ops_in_batch = 0
    for old_reminder_snap in existing_reminders_query:
        delete_batch.delete(old_reminder_snap.reference)
        deleted_old_count += 1
        ops_in_batch += 1
        if ops_in_batch >= 490:
            delete_batch.commit()
            delete_batch = db.batch()
            ops_in_batch = 0
    if ops_in_batch > 0:
        delete_batch.commit()
    logger.info(
        f"Deleted {deleted_old_count} old pending reminders for user {user_id}."
    )


def _store_new_reminders(
    db: firestore.Client,
    user_id: str,
    selected_matches: List[LLMSelectedFixtureResponse],
    original_fixtures_map: Dict[str, Dict],
    full_llm_prompt_text: str,
    llm_response_raw_text: str,
) -> int:
    """Stores the new reminders generated by the LLM in Firestore."""
    create_batch = db.batch()
    items_in_create_batch = 0
    reminders_created_count = 0
    created_at_ts = datetime.datetime.now(datetime.timezone.utc)

    for llm_match_info in selected_matches:
        original_fixture = original_fixtures_map.get(llm_match_info.fixture_id)
        if not original_fixture:
            logger.warning(
                f"LLM returned fixture_id {llm_match_info.fixture_id} not found in original fixtures map for user {user_id}. Skipping."
            )
            continue

        kickoff_time_utc_dt = original_fixture.get("match_datetime_utc")
        if not isinstance(kickoff_time_utc_dt, datetime.datetime):
            logger.warning(
                f"Fixture {llm_match_info.fixture_id} for user {user_id} has invalid kickoff_time_utc type: {type(kickoff_time_utc_dt)}. Skipping."
            )
            continue

        for trigger in llm_match_info.reminder_triggers:
            reminder_id = str(uuid.uuid4())
            actual_reminder_time = kickoff_time_utc_dt - datetime.timedelta(
                minutes=trigger.reminder_offset_minutes_before_kickoff
            )

            reminder_doc_data = {
                "reminder_id": reminder_id,
                "user_id": user_id,
                "fixture_id": llm_match_info.fixture_id,
                "reason_for_selection": llm_match_info.reason,
                "importance_score": llm_match_info.importance_score,
                "kickoff_time_utc": kickoff_time_utc_dt,
                "reminder_offset_minutes_before_kickoff": trigger.reminder_offset_minutes_before_kickoff,
                "reminder_mode": trigger.reminder_mode,
                "custom_message": trigger.custom_message,
                "actual_reminder_time_utc": actual_reminder_time,
                "status": "pending",
                "llm_prompt_used_brief": f"{full_llm_prompt_text[:200]}... (truncated)",
                "llm_response_snippet": (
                    llm_response_raw_text[:200] + "..."
                    if llm_response_raw_text
                    else "N/A"
                ),
                "created_at": created_at_ts,
                "updated_at": created_at_ts,
            }
            # reminder_pydantic_doc = ReminderDoc(**reminder_doc_data) # Optional: validate before storing

            doc_ref = db.collection(settings.REMINDERS_COLLECTION).document(reminder_id)
            create_batch.set(
                doc_ref, reminder_doc_data
            )  # reminder_pydantic_doc.model_dump() if validated
            reminders_created_count += 1
            items_in_create_batch += 1
            if items_in_create_batch >= 490:
                create_batch.commit()
                create_batch = db.batch()
                items_in_create_batch = 0

    if items_in_create_batch > 0:
        create_batch.commit()
    return reminders_created_count
