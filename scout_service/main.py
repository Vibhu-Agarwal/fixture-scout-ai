# scout_service/main.py

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import datetime
import uuid
import json
import os
import logging

from google.cloud import firestore

# Use Vertex AI SDK for Gemini
from google.cloud import aiplatform  # General SDK
import vertexai  # Specific Vertex AI functionalities
from vertexai.generative_models import (
    GenerativeModel,
    GenerationConfig,
    HarmCategory,
    HarmBlockThreshold,
    Part,  # For constructing prompts with mixed content if needed later
)

from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# --- Logging Configuration ---
# Get the logger for the current module
logger = logging.getLogger(__name__)
# Set default logging level (can be overridden by environment or specific handlers)
# For Cloud Run, logs at INFO level and above are typically captured by Cloud Logging.
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())


# --- Configuration ---
# Firestore Client
DATABASE_NAME = os.getenv("FIRESTORE_DATABASE_NAME")
if DATABASE_NAME:
    db = firestore.Client(database=DATABASE_NAME)
else:
    db = firestore.Client()

# Vertex AI Configuration
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION")  # Optional, some models are global, some regional

gemini_vertex_model = None
try:
    if not GCP_PROJECT_ID:
        raise ValueError("GCP_PROJECT_ID environment variable not set.")
    if not GCP_REGION:
        logger.warning(
            "GCP_REGION environment variable not set. Using default or global for Vertex AI."
        )
        # For some global models, location might not be strictly needed at init, but good practice.
        vertexai.init(
            project=GCP_PROJECT_ID
        )  # If region is truly optional for the model
    else:
        vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)

    GEMINI_MODEL_NAME_VERTEX = os.getenv("GEMINI_MODEL_NAME_VERTEX", "gemini-1.5-flash")
    gemini_vertex_model = GenerativeModel(GEMINI_MODEL_NAME_VERTEX)
    logger.info(
        f"Vertex AI Gemini model '{GEMINI_MODEL_NAME_VERTEX}' initialized in project '{GCP_PROJECT_ID}' region '{GCP_REGION}'."
    )
except Exception as e:
    logger.error(
        f"Could not initialize Vertex AI Gemini client. Error: {e}", exc_info=True
    )


app = FastAPI(
    title="Scout Service",
    description="Processes fixtures using an LLM (Gemini via Vertex AI) to create personalized reminders.",
    version="0.1.0",
)


# --- Pydantic Models ---
class FixtureForLLM(BaseModel):
    fixture_id: str
    home_team_name: str
    away_team_name: str
    league_name: str
    match_datetime_utc_str: str  # String representation for easier LLM consumption
    stage: Optional[str] = None
    raw_metadata_blob: Optional[Dict[str, Any]] = None


class LLMReminderTrigger(BaseModel):
    reminder_offset_minutes_before_kickoff: int = Field(..., examples=[60, 1440])
    reminder_mode: str = Field(..., examples=["email", "phone_call_mock"])
    custom_message: str = Field(..., examples=["Big match coming up! Get ready."])


class LLMSelectedFixtureResponse(BaseModel):
    fixture_id: str
    reason: str = Field(..., examples=["Key match for your favorite team Real Madrid."])
    importance_score: int = Field(..., ge=1, le=5, examples=[4])
    reminder_triggers: List[LLMReminderTrigger]


class ScoutRequest(BaseModel):
    user_id: str
    # For Phase 1, we will fetch fixtures inside the endpoint
    # Later, we might pass fixtures_to_consider if this is called by an orchestrator


# --- Firestore Collection Names ---
USERS_COLLECTION = "users"
USER_PREFERENCES_COLLECTION = "user_preferences"
FIXTURES_COLLECTION = "fixtures"
REMINDERS_COLLECTION = "reminders"


# --- Helper Functions ---
def _construct_gemini_prompt_vertex(
    user_optimized_prompt: str, fixtures: List[FixtureForLLM]
) -> str:
    fixtures_json_str = json.dumps([f.model_dump() for f in fixtures], indent=2)

    prompt = f"""
You are Fixture Scout AI. Your task is to select relevant football matches for a user based on their preferences and a list of upcoming fixtures.
For each match you select, you must provide a brief reason for the selection, assign an importance score, and define specific reminder triggers.

User's Match Selection Criteria:
"{user_optimized_prompt}"

Available Upcoming Fixtures:
{fixtures_json_str}

Instructions for your response:
1. Analyze the user's criteria and the available fixtures.
2. Select ONLY the matches that fit the user's criteria.
3. For EACH selected match, provide:
    a. "fixture_id": The exact fixture_id from the input.
    b. "reason": A brief (1-2 sentences, max 100 characters) explanation of why this match is relevant to the user based on their criteria (e.g., "Important Real Madrid La Liga game.", "Potential title decider in Premier League.", "Champions League clash between top teams.").
    c. "importance_score": An integer from 1 (mildly interesting) to 5 (critically important).
       Consider the user's favorite team, major rivalries, Champions League significance, title deciders, derbies, or unique metadata.
    d. "reminder_triggers": An array of objects. Each object must have:
        i. "reminder_offset_minutes_before_kickoff": How many minutes before kickoff to send the reminder (e.g., 1440 for 24 hours, 60 for 1 hour, 120 for 2 hours).
           - For importance 4-5, consider a reminder 24h before AND 1-2h before.
           - For importance 3, maybe one reminder 2-4h before.
           - For importance 1-2, maybe one reminder 24h before or a few hours before.
        ii. "reminder_mode": String, either "email" or "phone_call_mock".
            - Use "phone_call_mock" ONLY for very important matches (e.g., importance 5, and for the reminder closest to kickoff, like 1 hour before).
            - Otherwise, use "email".
        iii. "custom_message": A short, engaging, personalized message for the reminder (max 150 characters). This message can incorporate elements from your "reason". Example: "Heads up! El Clasico (Real Madrid vs Barcelona) is tomorrow! A must-watch."

Output Format:
Provide your response as a VALID JSON ARRAY of selected matches. Each element in the array should be an object strictly following this structure:
{{
  "fixture_id": "string",
  "reason": "string",
  "importance_score": integer,
  "reminder_triggers": [
    {{
      "reminder_offset_minutes_before_kickoff": integer,
      "reminder_mode": "string",
      "custom_message": "string"
    }}
  ]
}}

If no matches meet the criteria, output an empty JSON array: [].
DO NOT include any explanations or text outside of the JSON array.
"""
    return prompt


LOOKOUT_WINDOW = 14  # Days to look ahead for fixtures


# --- API Endpoint ---
@app.post("/scout/process-user-fixtures", status_code=200)
async def process_user_fixtures(request: ScoutRequest = Body(...)):
    if not db:
        logger.error("Firestore client not initialized during request.")
        raise HTTPException(status_code=500, detail="Firestore client not initialized.")
    if not gemini_vertex_model:
        logger.error("Vertex AI Gemini client not initialized during request.")
        raise HTTPException(
            status_code=500, detail="Vertex AI Gemini client not initialized."
        )

    user_id = request.user_id
    logger.info(f"Starting scout processing for user_id: {user_id}")

    # 1. Fetch user's preference
    preference_doc_ref = db.collection(USER_PREFERENCES_COLLECTION).document(user_id)
    preference_doc = preference_doc_ref.get()
    if not preference_doc.exists:
        logger.warning(f"Preferences for user ID {user_id} not found.")
        raise HTTPException(
            status_code=404, detail=f"Preferences for user ID {user_id} not found."
        )
    user_preferences = preference_doc.to_dict()
    optimized_llm_prompt_text = user_preferences.get("optimized_llm_prompt")
    if not optimized_llm_prompt_text:
        logger.error(f"Optimized LLM prompt not set for user {user_id}.")
        raise HTTPException(
            status_code=400, detail=f"Optimized LLM prompt not set for user {user_id}."
        )
    logger.debug(
        f"User {user_id} optimized prompt: {optimized_llm_prompt_text[:200]}..."
    )

    # 2. Fetch upcoming fixtures
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    future_cutoff_utc = now_utc + datetime.timedelta(days=LOOKOUT_WINDOW)
    logger.info(
        f"Fetching fixtures between {now_utc.isoformat()} and {future_cutoff_utc.isoformat()}"
    )

    fixtures_query = (
        db.collection(FIXTURES_COLLECTION)
        .where("match_datetime_utc", ">=", now_utc)
        .where("match_datetime_utc", "<=", future_cutoff_utc)
        .order_by("match_datetime_utc")
        .stream()
    )

    upcoming_fixtures_for_llm: List[FixtureForLLM] = []
    # Keep a map of original fixture details for creating reminders
    original_fixtures_map: Dict[str, Dict] = {}

    for fixture_snap in fixtures_query:
        fixture_data = fixture_snap.to_dict()
        original_fixtures_map[fixture_data["fixture_id"]] = fixture_data

        # Convert datetime to string for LLM, ensure it's UTC and clearly formatted
        match_dt_utc = fixture_data.get("match_datetime_utc")
        match_datetime_utc_str = (
            match_dt_utc.isoformat()
            if isinstance(match_dt_utc, datetime.datetime)
            else str(match_dt_utc)
        )
        upcoming_fixtures_for_llm.append(
            FixtureForLLM(
                fixture_id=fixture_data["fixture_id"],
                home_team_name=fixture_data.get("home_team", {}).get(
                    "name", "Unknown Home"
                ),
                away_team_name=fixture_data.get("away_team", {}).get(
                    "name", "Unknown Away"
                ),
                league_name=fixture_data.get("league_name", "Unknown League"),
                match_datetime_utc_str=match_datetime_utc_str,
                stage=fixture_data.get("stage"),
                raw_metadata_blob=fixture_data.get("raw_metadata_blob"),
            )
        )
    logger.info(
        f"Fetched {len(upcoming_fixtures_for_llm)} upcoming fixtures for LLM processing."
    )

    if not upcoming_fixtures_for_llm:
        logger.info(
            f"No upcoming fixtures found in the database to process for user {user_id}."
        )
        return {
            "message": f"No upcoming fixtures found in the database to process for user {user_id}."
        }

    # 3. Construct the prompt for Gemini
    full_llm_prompt = _construct_gemini_prompt_vertex(
        optimized_llm_prompt_text, upcoming_fixtures_for_llm
    )
    logger.debug(
        f"Constructed LLM prompt for user {user_id} (first 500 chars): {full_llm_prompt[:500]}..."
    )

    # 4. Call Gemini API via Vertex AI
    llm_response_raw_text = ""
    selected_matches_from_llm: List[LLMSelectedFixtureResponse] = []
    try:
        logger.info(
            f"Sending prompt to Vertex AI Gemini for user {user_id} (model: {GEMINI_MODEL_NAME_VERTEX})."
        )

        generation_config_vertex = GenerationConfig(
            temperature=0.2,  # Slightly lower for more deterministic JSON
            max_output_tokens=4096,  # Max tokens to generate
            # top_p=0.95,
            # top_k=40
        )

        safety_settings_vertex = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,  # Adjusted for potentially more leniency if needed
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

        # Vertex AI SDK's generate_content can take a string directly
        response = gemini_vertex_model.generate_content(
            full_llm_prompt,  # Pass the string prompt
            generation_config=generation_config_vertex,
            safety_settings=safety_settings_vertex,
            stream=False,
        )

        if hasattr(response, "text") and response.text:
            llm_response_raw_text = response.text
        else:
            llm_response_raw_text = "[]"
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                logger.warning(
                    f"Prompt for user {user_id} was blocked by Vertex AI. Reason: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}"
                )
            elif (
                not response.candidates
                or not hasattr(response.candidates[0], "content")
                or not response.candidates[0].content.parts
            ):
                logger.warning(
                    f"Vertex AI Gemini response for user {user_id} was empty or malformed (no content parts in candidate)."
                )

        logger.info(
            f"Raw LLM response snippet for user {user_id}: {llm_response_raw_text[:300]}..."
        )
        logger.debug(
            f"Full raw LLM response for user {user_id}:\n{llm_response_raw_text}"
        )

        # 5. Parse the structured JSON response
        cleaned_response_str = llm_response_raw_text.strip()
        if cleaned_response_str.startswith("```json"):
            cleaned_response_str = cleaned_response_str[7:]
        if cleaned_response_str.startswith("```"):  # handles cases like ```\njson...
            cleaned_response_str = cleaned_response_str[3:]
        if cleaned_response_str.endswith("```"):
            cleaned_response_str = cleaned_response_str[:-3]
        cleaned_response_str = cleaned_response_str.strip()

        if not cleaned_response_str:
            logger.warning(f"LLM response was empty after cleaning for user {user_id}.")
            selected_matches_from_llm_data = []
        else:
            try:
                selected_matches_from_llm_data = json.loads(cleaned_response_str)
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse LLM JSON response for user {user_id}: {e}. Problematic JSON string: '{cleaned_response_str}'",
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"LLM returned invalid JSON. Raw response: {llm_response_raw_text}",
                )

        for item_data in selected_matches_from_llm_data:
            try:
                selected_matches_from_llm.append(
                    LLMSelectedFixtureResponse(**item_data)
                )
            except Exception as e:
                logger.warning(
                    f"Skipping item from LLM due to Pydantic validation error: {item_data}, Error: {e}",
                    exc_info=True,
                )
                continue

    except Exception as e:
        logger.error(
            f"Exception during Vertex AI Gemini API call or processing for user {user_id}: {str(e)}",
            exc_info=True,
        )
        error_prompt_log_snippet = (
            full_llm_prompt[:1000]
            if "full_llm_prompt" in locals()
            else "Prompt not generated."
        )
        logger.debug(
            f"LLM Prompt that may have caused error (first 1000 chars): {error_prompt_log_snippet}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error interacting with LLM via Vertex AI: {str(e)}",
        )

    # 6. Store the generated reminder instructions in Firestore
    reminders_created_count = 0
    if selected_matches_from_llm:
        logger.info(
            f"LLM selected {len(selected_matches_from_llm)} matches for user {user_id}. Storing reminders."
        )

        # Idempotency: Clear old "pending" reminders for this user for the processed fixtures
        # This is a simple approach. A more complex one would update existing reminders.
        # For now, if we re-process, we create new ones. Consider how to handle this if a fixture
        # is processed multiple times over its lifecycle (e.g. if its time changes).
        # A better strategy might be to delete pending reminders only for fixture_ids
        # that appear in the new LLM response or were part of the input fixtures.

        # Let's delete any existing 'pending' reminders for the fixtures that were part of this LLM run
        # This prevents duplicates if the scout is run multiple times for the same fixtures.
        fixture_ids_in_llm_input = [f.fixture_id for f in upcoming_fixtures_for_llm]
        if fixture_ids_in_llm_input:
            existing_reminders_query = (
                db.collection(REMINDERS_COLLECTION)
                .where("user_id", "==", user_id)
                .where("fixture_id", "in", fixture_ids_in_llm_input)
                .where("status", "==", "pending")
                .stream()
            )

            delete_batch = db.batch()
            deleted_old_count = 0
            operations_in_current_delete_batch = 0  # Initialize counter for this batch

            for old_reminder_snap in existing_reminders_query:
                delete_batch.delete(old_reminder_snap.reference)
                deleted_old_count += 1
                operations_in_current_delete_batch += 1

                if operations_in_current_delete_batch >= 490:  # Firestore batch limit
                    delete_batch.commit()
                    delete_batch = db.batch()  # Start a new batch
                    operations_in_current_delete_batch = 0  # Reset counter

            # After the loop, commit if there are any remaining operations in the current batch
            if operations_in_current_delete_batch > 0:
                delete_batch.commit()

            logger.info(
                f"Deleted {deleted_old_count} old pending reminders for user {user_id} for the processed fixtures."
            )

        # Now, create new reminders from LLM output
        create_batch = db.batch()
        items_in_create_batch = 0
        created_at_ts = datetime.datetime.now(datetime.timezone.utc)

        for llm_match_info in selected_matches_from_llm:
            original_fixture = original_fixtures_map.get(llm_match_info.fixture_id)
            if not original_fixture:
                logger.warning(
                    f"LLM returned fixture_id {llm_match_info.fixture_id} not found in original fixtures. Skipping."
                )
                continue

            kickoff_time_utc_dt = original_fixture.get("match_datetime_utc")
            if not isinstance(kickoff_time_utc_dt, datetime.datetime):
                logger.warning(
                    f"Fixture {llm_match_info.fixture_id} has invalid kickoff_time_utc type: {type(kickoff_time_utc_dt)}. Skipping."
                )
                continue

            for trigger in llm_match_info.reminder_triggers:
                reminder_id = str(uuid.uuid4())
                actual_reminder_time = kickoff_time_utc_dt - datetime.timedelta(
                    minutes=trigger.reminder_offset_minutes_before_kickoff
                )

                reminder_doc = {
                    "reminder_id": reminder_id,
                    "user_id": user_id,
                    "fixture_id": llm_match_info.fixture_id,
                    "reason_for_selection": llm_match_info.reason,  # Added reason
                    "importance_score": llm_match_info.importance_score,
                    "kickoff_time_utc": kickoff_time_utc_dt,
                    "reminder_offset_minutes_before_kickoff": trigger.reminder_offset_minutes_before_kickoff,
                    "reminder_mode": trigger.reminder_mode,
                    "custom_message": trigger.custom_message,
                    "actual_reminder_time_utc": actual_reminder_time,
                    "status": "pending",
                    "llm_prompt_used_brief": f"{full_llm_prompt[:200]}... (truncated)",
                    # Consider if full raw response is needed or just a snippet/flag for errors
                    "llm_response_snippet": (
                        llm_response_raw_text[:200] + "..."
                        if llm_response_raw_text
                        else "N/A"
                    ),
                    "created_at": created_at_ts,
                    "updated_at": created_at_ts,
                }
                doc_ref = db.collection(REMINDERS_COLLECTION).document(reminder_id)
                create_batch.set(doc_ref, reminder_doc)
                reminders_created_count += 1
                items_in_create_batch += 1
                if items_in_create_batch >= 490:
                    create_batch.commit()
                    create_batch = db.batch()
                    items_in_create_batch = 0

        if items_in_create_batch > 0:
            create_batch.commit()
        logger.info(
            f"Created {reminders_created_count} new reminder entries for user {user_id}."
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


@app.get("/")
async def read_root():
    return {
        "message": "Welcome to the Fixture Scout AI - Scout Service (Vertex AI Enhanced)"
    }
