# scout_service/app/services/reminder_processing_service.py
import logging
import datetime
import uuid
import json
from typing import List, Dict, Tuple, Optional

from pydantic import ValidationError  # For catching Pydantic validation errors
from google.cloud import firestore
from vertexai.generative_models import (
    GenerativeModel,
    GenerationConfig,
    HarmCategory,
    HarmBlockThreshold,
)

from ..config import settings
from ..firestore_client import get_firestore_client
from ..vertex_ai_client import get_vertex_ai_gemini_client
from ..llm_prompts import construct_gemini_scout_prompt
from ..models import (
    FixtureForLLM,
    LLMSelectedFixtureResponse,
    UserPreferenceDoc,
    FixtureDoc,
    ReminderDoc,
)

logger = logging.getLogger(__name__)


class ReminderProcessingError(Exception):
    """Custom exception for errors during reminder processing."""

    pass


class LLMResponseError(ReminderProcessingError):
    """Custom exception for issues with LLM response."""

    pass


class DataValidationError(ReminderProcessingError):
    """Custom exception for data validation errors from Firestore."""

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
    logger.info(f"Processing fixtures for user {user_id}...")

    db = get_firestore_client()
    gemini_model = get_vertex_ai_gemini_client()

    # 1. Fetch user's preference
    user_pref_doc = _fetch_user_preference_doc(db, user_id)
    if not user_pref_doc or not user_pref_doc.optimized_llm_prompt:
        raise ReminderProcessingError(
            f"User preferences or optimized LLM prompt not found/invalid for user ID {user_id}."
        )
    optimized_llm_prompt_text = user_pref_doc.optimized_llm_prompt

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

    llm_response_raw_text, selected_matches_from_llm = (
        await _call_llm_and_parse_response(gemini_model, full_llm_prompt, user_id)
    )

    # 4. Store reminders
    reminders_created_count = 0
    if selected_matches_from_llm:
        await _clear_old_pending_reminders(
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


def _fetch_user_preference_doc(
    db: firestore.Client, user_id: str
) -> Optional[UserPreferenceDoc]:
    """Fetches and validates the user preference document."""
    preference_doc_ref = db.collection(settings.USER_PREFERENCES_COLLECTION).document(
        user_id
    )
    preference_snap = preference_doc_ref.get()

    if not preference_snap.exists:
        logger.warning(f"Preferences document for user ID {user_id} not found.")
        return None

    try:
        user_pref_data = preference_snap.to_dict()
        user_pref_doc = UserPreferenceDoc(**user_pref_data)
        logger.debug(f"User {user_id} preferences fetched and validated.")
        return user_pref_doc
    except ValidationError as e:
        logger.error(
            f"Validation error for user preference doc {user_id}: {e}", exc_info=True
        )
        raise DataValidationError(f"Invalid user preference data for user {user_id}.")
    except Exception as e:  # Catch any other unexpected error during fetching/parsing
        logger.error(
            f"Unexpected error fetching user preference doc {user_id}: {e}",
            exc_info=True,
        )
        raise ReminderProcessingError(
            f"Could not retrieve user preferences for {user_id}."
        )


def _fetch_upcoming_fixtures(
    db: firestore.Client,
) -> Tuple[List[FixtureForLLM], Dict[str, FixtureDoc]]:
    """Fetches upcoming fixtures from Firestore, validates them, and prepares them for the LLM."""
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
    original_fixtures_map: Dict[str, FixtureDoc] = {}

    for fixture_snap in fixtures_query:
        fixture_data_dict = None
        try:
            fixture_data_dict = fixture_snap.to_dict()
            # Validate fixture data against FixtureDoc model
            fixture_doc = FixtureDoc(**fixture_data_dict)
            original_fixtures_map[fixture_doc.fixture_id] = fixture_doc

            match_datetime_utc_str = fixture_doc.match_datetime_utc.isoformat()

            upcoming_fixtures_for_llm.append(
                FixtureForLLM(
                    fixture_id=fixture_doc.fixture_id,
                    home_team_name=fixture_doc.home_team.get("name", "Unknown Home"),
                    away_team_name=fixture_doc.away_team.get("name", "Unknown Away"),
                    league_name=fixture_doc.league_name,
                    match_datetime_utc_str=match_datetime_utc_str,
                    stage=fixture_doc.stage,
                    raw_metadata_blob=fixture_doc.raw_metadata_blob,
                )
            )
        except ValidationError as e:
            logger.error(
                f"Validation error for fixture doc {fixture_snap.id}: {e}. Data: {fixture_data_dict}",
                exc_info=True,
            )
            # Optionally, raise DataValidationError or just skip
            continue  # Skip this fixture if it's invalid
        except Exception as e:
            logger.error(
                f"Error processing fixture {fixture_snap.id}: {e}", exc_info=True
            )
            continue

    logger.info(
        f"Fetched and validated {len(upcoming_fixtures_for_llm)} upcoming fixtures for LLM."
    )
    return upcoming_fixtures_for_llm, original_fixtures_map


async def _call_llm_and_parse_response(
    gemini_model: GenerativeModel, full_llm_prompt: str, user_id: str
) -> Tuple[str, List[LLMSelectedFixtureResponse]]:
    """Calls the LLM and parses its JSON response."""
    try:
        logger.info(
            f"Sending prompt to Vertex AI Gemini for user {user_id} (model: {settings.GEMINI_MODEL_NAME_VERTEX})."
        )
        generation_config = GenerationConfig(
            temperature=0.2,
            max_output_tokens=8192,
            # top_p=0.95,
            # top_k=40
        )
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

        response = await gemini_model.generate_content_async(
            full_llm_prompt,
            generation_config=generation_config,
            safety_settings=safety_settings,
            stream=False,  # stream=True would also be async and return an AsyncIterable
        )

        llm_response_raw_text = ""
        # The response structure for async might be slightly different or handled the same way
        # Assuming response.text is still the way to get it for non-streaming async
        if hasattr(response, "text") and response.text:
            llm_response_raw_text = response.text
        else:
            llm_response_raw_text = "[]"
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
            ):  # Check this structure based on SDK docs for async if it differs
                logger.warning(
                    f"Vertex AI Gemini response for user {user_id} was empty or malformed (no content parts)."
                )

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
        except ValidationError as e:
            logger.error(
                f"Error validating LLM response structure for user {user_id}: {e}",
                exc_info=True,
            )
            raise LLMResponseError(f"LLM response structure invalid. Error: {e}")

    except Exception as e:
        logger.error(
            f"Exception during Vertex AI Gemini API call or parsing for user {user_id}: {str(e)}",
            exc_info=True,
        )
        if not isinstance(e, LLMResponseError):
            raise LLMResponseError(f"General error during LLM interaction: {str(e)}")
        else:
            raise e


async def _clear_old_pending_reminders(  # Make it async if db operations become async later, for now it's fine
    db: firestore.Client, user_id: str, fixture_ids_in_llm_input: List[str]
):
    """Deletes old 'pending' reminders for the given user and fixture IDs."""
    if not fixture_ids_in_llm_input:
        logger.info(
            f"No fixture IDs provided to clear old reminders for user {user_id}."
        )
        return

    logger.info(
        f"Clearing old pending reminders for user {user_id} for {len(fixture_ids_in_llm_input)} potential fixture IDs."
    )

    MAX_IN_QUERY_VALUES = 30  # Firestore limit for 'IN' operator
    total_deleted_old_count = 0

    # Process fixture_ids in chunks
    for i in range(0, len(fixture_ids_in_llm_input), MAX_IN_QUERY_VALUES):
        chunk_fixture_ids = fixture_ids_in_llm_input[i : i + MAX_IN_QUERY_VALUES]

        logger.debug(
            f"Processing chunk {i} of {len(chunk_fixture_ids)} fixture IDs for user {user_id} to clear old reminders."
        )

        try:
            existing_reminders_query = (
                db.collection(settings.REMINDERS_COLLECTION)
                .where("user_id", "==", user_id)
                .where("fixture_id", "in", chunk_fixture_ids)
                .where("status", "==", "pending")
                .stream()  # This is a synchronous call
            )

            # Collect references to delete in batches to avoid too many individual writes
            # and to respect Firestore batch limits for writes (500 ops per batch)
            docs_to_delete_refs = [
                old_reminder_snap.reference
                for old_reminder_snap in existing_reminders_query
            ]

            if not docs_to_delete_refs:
                logger.debug(
                    f"No 'pending' reminders found for user {user_id} in fixture ID chunk: {chunk_fixture_ids}"
                )
                continue

            logger.info(
                f"Found {len(docs_to_delete_refs)} old 'pending' reminders to delete for user {user_id} in current chunk."
            )

            delete_batch = db.batch()
            ops_in_current_write_batch = 0
            MAX_OPS_PER_WRITE_BATCH = 490  # Firestore write batch limit

            for doc_ref in docs_to_delete_refs:
                delete_batch.delete(doc_ref)
                ops_in_current_write_batch += 1
                total_deleted_old_count += 1  # Increment total count here

                if ops_in_current_write_batch >= MAX_OPS_PER_WRITE_BATCH:
                    delete_batch.commit()  # Synchronous call
                    logger.info(
                        f"Committed a delete batch of {ops_in_current_write_batch} old reminders for user {user_id}."
                    )
                    delete_batch = db.batch()  # Start a new write batch
                    ops_in_current_write_batch = 0

            # Commit any remaining operations in the last write batch for this chunk
            if ops_in_current_write_batch > 0:
                delete_batch.commit()  # Synchronous call
                logger.info(
                    f"Committed final delete batch of {ops_in_current_write_batch} old reminders for user {user_id} from chunk."
                )

        except Exception as e:
            logger.error(
                f"Error processing a chunk of fixture IDs ({chunk_fixture_ids}) for user {user_id} while clearing old reminders: {e}",
                exc_info=True,
            )
            # Decide if you want to continue with other chunks or stop.
            # For now, we'll log and continue with the next chunk.
            continue

    logger.info(
        f"Finished clearing old reminders. Total deleted: {total_deleted_old_count} old pending reminders for user {user_id} across all chunks."
    )


def _store_new_reminders(
    db: firestore.Client,
    user_id: str,
    selected_matches: List[LLMSelectedFixtureResponse],
    original_fixtures_map: Dict[str, FixtureDoc],
    full_llm_prompt_text: str,
    llm_response_raw_text: str,
) -> int:
    """Stores the new reminders (validated with ReminderDoc) generated by the LLM in Firestore."""
    create_batch = db.batch()
    items_in_create_batch = 0
    reminders_created_count = 0
    created_at_ts = datetime.datetime.now(datetime.timezone.utc)

    for llm_match_info in selected_matches:
        original_fixture_doc = original_fixtures_map.get(llm_match_info.fixture_id)
        if not original_fixture_doc:
            logger.warning(
                f"LLM returned fixture_id {llm_match_info.fixture_id} not found in original fixtures map for user {user_id}. Skipping."
            )
            continue

        kickoff_time_utc_dt = original_fixture_doc.match_datetime_utc

        for trigger in llm_match_info.reminder_triggers:
            reminder_id = str(uuid.uuid4())
            actual_reminder_time = kickoff_time_utc_dt - datetime.timedelta(
                minutes=trigger.reminder_offset_minutes_before_kickoff
            )

            try:
                reminder_data = ReminderDoc(
                    reminder_id=reminder_id,
                    user_id=user_id,
                    fixture_id=llm_match_info.fixture_id,
                    reason_for_selection=llm_match_info.reason,
                    importance_score=llm_match_info.importance_score,
                    kickoff_time_utc=kickoff_time_utc_dt,
                    reminder_offset_minutes_before_kickoff=trigger.reminder_offset_minutes_before_kickoff,
                    reminder_mode=trigger.reminder_mode,
                    custom_message=trigger.custom_message,
                    actual_reminder_time_utc=actual_reminder_time,
                    status="pending",  # Default status
                    llm_prompt_used_brief=f"{full_llm_prompt_text[:200]}... (truncated)",
                    llm_response_snippet=(
                        llm_response_raw_text[:200] + "..."
                        if llm_response_raw_text
                        else "N/A"
                    ),
                    created_at=created_at_ts,
                    updated_at=created_at_ts,
                )
                doc_ref = db.collection(settings.REMINDERS_COLLECTION).document(
                    reminder_id
                )
                # Use model_dump() to get a dict suitable for Firestore
                create_batch.set(doc_ref, reminder_data.model_dump())
                reminders_created_count += 1
                items_in_create_batch += 1

                if items_in_create_batch >= 490:
                    create_batch.commit()
                    create_batch = db.batch()
                    items_in_create_batch = 0
            except ValidationError as e:
                logger.error(
                    f"Validation error creating reminder doc for fixture {llm_match_info.fixture_id}, user {user_id}: {e}",
                    exc_info=True,
                )
                # Decide if to skip this specific reminder or halt
                continue  # Skip this reminder trigger

    if items_in_create_batch > 0:
        create_batch.commit()
    return reminders_created_count
