# scout_service/main.py

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import datetime
import uuid
import json
import os

from google.cloud import firestore
import google.generativeai as genai  # Using the new standalone Gemini SDK

# --- Configuration ---
# Firestore Client
DATABASE_NAME = os.getenv("FIRESTORE_DATABASE_NAME")
try:
    if DATABASE_NAME:
        db = firestore.Client(database=DATABASE_NAME)
    else:
        db = firestore.Client()
except Exception as e:
    print(f"Could not initialize Firestore client. Error: {e}")
    db = None

# Gemini API Configuration
# Make sure to set your GOOGLE_API_KEY environment variable
# You can get an API key from Google AI Studio: https://aistudio.google.com/app/apikey
# For production on GCP, consider using Vertex AI SDK with service accounts for better security and integration.
# For this phase, we'll use the standalone Gemini SDK for simplicity.
try:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    genai.configure(api_key=GOOGLE_API_KEY)
    # For `gemini-pro` (text-only), but you might use `gemini-1.5-pro-latest` or `gemini-1.0-pro`
    # Ensure the model name is one available through the API key.
    # Common models: "gemini-pro", "gemini-1.0-pro", "gemini-1.5-flash-latest", "gemini-1.5-pro-latest"
    # For this example, let's use a widely available one:
    GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.0-pro")
    gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    print(f"Gemini model '{GEMINI_MODEL_NAME}' initialized.")
except Exception as e:
    print(f"Could not initialize Gemini client. Error: {e}")
    gemini_model = None


app = FastAPI(
    title="Scout Service",
    description="Processes fixtures using an LLM (Gemini) to create personalized reminders.",
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
    # raw_metadata_blob: Optional[Dict[str, Any]] = None # Keep it simple for now for the prompt


class LLMReminderTrigger(BaseModel):
    reminder_offset_minutes_before_kickoff: int = Field(..., example=60)
    reminder_mode: str = Field(..., example="email")  # "email", "phone_call_mock"
    custom_message: str = Field(..., example="Big match coming up!")


class LLMSelectedFixtureResponse(BaseModel):
    fixture_id: str
    importance_score: int = Field(..., ge=1, le=5, example=4)  # Score 1-5
    reminder_triggers: List[LLMReminderTrigger]


class ScoutRequest(BaseModel):
    user_id: str
    # For Phase 1, we will fetch fixtures inside the endpoint
    # Later, we might pass fixtures_to_consider if this is called by an orchestrator


# --- Firestore Collection Names ---
USERS_COLLECTION = "users"  # To verify user exists
USER_PREFERENCES_COLLECTION = "user_preferences"
FIXTURES_COLLECTION = "fixtures"
REMINDERS_COLLECTION = "reminders"


# --- Helper Functions ---
def _construct_gemini_prompt(
    user_optimized_prompt: str, fixtures: List[FixtureForLLM]
) -> str:
    fixtures_json_str = json.dumps(
        [f.model_dump() for f in fixtures], indent=2
    )  # Pydantic v2

    prompt = f"""
You are Fixture Scout AI. Your task is to select relevant football matches for a user based on their preferences and a list of upcoming fixtures.
For each match you select, you must assign an importance score and define specific reminder triggers (when and how to remind).

User's Match Selection Criteria:
"{user_optimized_prompt}"

Available Upcoming Fixtures:
{fixtures_json_str}

Instructions for your response:
1. Analyze the user's criteria and the available fixtures.
2. Select ONLY the matches that fit the user's criteria.
3. For EACH selected match, provide:
    a. "fixture_id": The exact fixture_id from the input.
    b. "importance_score": An integer from 1 (mildly interesting) to 5 (critically important).
       Consider the user's favorite team (e.g., Real Madrid matches are usually 5), major rivalries (e.g., El Clasico),
       Champions League significance, title deciders, derbies, or unique metadata mentioned in the user's prompt.
    c. "reminder_triggers": An array of objects. Each object must have:
        i. "reminder_offset_minutes_before_kickoff": How many minutes before kickoff to send the reminder (e.g., 1440 for 24 hours, 60 for 1 hour, 120 for 2 hours).
           - For importance 4-5, consider a reminder 24h before AND 1-2h before.
           - For importance 3, maybe one reminder 2-4h before.
           - For importance 1-2, maybe one reminder 24h before or a few hours before.
        ii. "reminder_mode": String, either "email" or "phone_call_mock".
            - Use "phone_call_mock" ONLY for 매우 important matches (e.g., importance 5, like a Real Madrid vs Barcelona match, and for the reminder closest to kickoff, like 1 hour before).
            - Otherwise, use "email".
        iii. "custom_message": A short, engaging, personalized message for the reminder (max 150 characters). Example: "Heads up! El Clasico (Real Madrid vs Barcelona) is tomorrow!" or "CRITICAL: Real Madrid vs Barca in 1 hour!".

Output Format:
Provide your response as a VALID JSON ARRAY of selected matches. Each element in the array should be an object strictly following this structure:
{{
  "fixture_id": "string",
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


# --- API Endpoint ---
@app.post("/scout/process-user-fixtures", status_code=200)
async def process_user_fixtures(request: ScoutRequest = Body(...)):
    if not db:
        raise HTTPException(status_code=500, detail="Firestore client not initialized.")
    if not gemini_model:
        raise HTTPException(status_code=500, detail="Gemini client not initialized.")

    user_id = request.user_id

    # 1. Fetch user's preference
    preference_doc_ref = db.collection(USER_PREFERENCES_COLLECTION).document(user_id)
    preference_doc = preference_doc_ref.get()
    if not preference_doc.exists:
        raise HTTPException(
            status_code=404, detail=f"Preferences for user ID {user_id} not found."
        )
    user_preferences = preference_doc.to_dict()
    optimized_llm_prompt = user_preferences.get("optimized_llm_prompt")
    if not optimized_llm_prompt:
        raise HTTPException(
            status_code=400, detail=f"Optimized LLM prompt not set for user {user_id}."
        )

    # 2. Fetch upcoming fixtures (e.g., next 7-14 days)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    future_cutoff_utc = now_utc + datetime.timedelta(
        days=14
    )  # Consider fixtures in the next 14 days

    fixtures_query = (
        db.collection(FIXTURES_COLLECTION)
        .where("match_datetime_utc", ">=", now_utc)
        .where("match_datetime_utc", "<=", future_cutoff_utc)
        .order_by("match_datetime_utc")
        .stream()
    )  # Use stream() for iterator

    upcoming_fixtures_for_llm: List[FixtureForLLM] = []
    # Keep a map of original fixture details for creating reminders
    original_fixtures_map: Dict[str, Dict] = {}

    for fixture_snap in fixtures_query:
        fixture_data = fixture_snap.to_dict()
        original_fixtures_map[fixture_data["fixture_id"]] = fixture_data

        # Convert datetime to string for LLM, ensure it's UTC and clearly formatted
        match_dt_utc = fixture_data.get("match_datetime_utc")
        if isinstance(match_dt_utc, datetime.datetime):
            match_datetime_utc_str = match_dt_utc.isoformat()
        else:  # Fallback if it's already a string or other type (less ideal)
            match_datetime_utc_str = str(match_dt_utc)

        upcoming_fixtures_for_llm.append(
            FixtureForLLM(
                fixture_id=fixture_data["fixture_id"],
                home_team_name=fixture_data["home_team"][
                    "name"
                ],  # Assuming nested structure
                away_team_name=fixture_data["away_team"][
                    "name"
                ],  # Assuming nested structure
                league_name=fixture_data["league_name"],
                match_datetime_utc_str=match_datetime_utc_str,
                stage=fixture_data.get("stage"),
                # raw_metadata_blob=fixture_data.get("raw_metadata_blob") # Consider adding if useful
            )
        )

    if not upcoming_fixtures_for_llm:
        return {
            "message": f"No upcoming fixtures found in the database to process for user {user_id}."
        }

    # 3. Construct the prompt for Gemini
    full_llm_prompt = _construct_gemini_prompt(
        optimized_llm_prompt, upcoming_fixtures_for_llm
    )

    # 4. Call Gemini API
    llm_response_raw = ""
    selected_matches_from_llm: List[LLMSelectedFixtureResponse] = []
    try:
        print(
            f"Sending prompt to Gemini for user {user_id}:\n{full_llm_prompt[:1000]}..."
        )  # Log beginning of prompt

        # Configuration for safer generation (optional, but good practice)
        generation_config = genai.types.GenerationConfig(
            # Only one candidate for now.
            candidate_count=1,
            # Stop sequences to prevent runaway generation.
            # stop_sequences=['x'],
            # Maximum number of tokens to generate.
            # max_output_tokens=2048, # Default is often fine for structured JSON
            temperature=0.3,  # Lower temperature for more deterministic JSON output
            # top_p=1,
            # top_k=1
        )
        # Safety settings (adjust as needed)
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
        ]

        response = gemini_model.generate_content(
            full_llm_prompt,
            generation_config=generation_config,
            safety_settings=safety_settings,
        )

        # Accessing the response text for Gemini API
        if response.parts:
            llm_response_raw = "".join(
                part.text for part in response.parts if hasattr(part, "text")
            )
        elif (
            hasattr(response, "text") and response.text
        ):  # Fallback for older/different response structures
            llm_response_raw = response.text
        else:
            # Handle cases where response might be blocked or empty
            llm_response_raw = "[]"  # Assume empty if no text parts
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                print(
                    f"Prompt was blocked. Reason: {response.prompt_feedback.block_reason}"
                )
                # Potentially raise an error or return a specific message
            elif not response.candidates or not response.candidates[0].content.parts:
                print("Gemini response was empty or malformed (no content parts).")

        print(f"Raw LLM response for user {user_id}:\n{llm_response_raw}")

        # 5. Parse the structured JSON response
        # Clean the response: Gemini might sometimes include ```json ... ```
        cleaned_response_str = llm_response_raw.strip()
        if cleaned_response_str.startswith("```json"):
            cleaned_response_str = cleaned_response_str[7:]
        if cleaned_response_str.startswith("```"):  # handles cases like ```\njson...
            cleaned_response_str = cleaned_response_str[3:]
        if cleaned_response_str.endswith("```"):
            cleaned_response_str = cleaned_response_str[:-3]
        cleaned_response_str = cleaned_response_str.strip()

        if not cleaned_response_str:  # If after cleaning, string is empty
            print(f"LLM response was empty after cleaning for user {user_id}.")
            selected_matches_from_llm_data = []
        else:
            try:
                selected_matches_from_llm_data = json.loads(cleaned_response_str)
            except json.JSONDecodeError as e:
                print(
                    f"ERROR: Failed to parse LLM JSON response for user {user_id}: {e}"
                )
                print(f"Problematic JSON string: '{cleaned_response_str}'")
                raise HTTPException(
                    status_code=500,
                    detail=f"LLM returned invalid JSON. Raw response: {llm_response_raw}",
                )

        # Validate with Pydantic
        for item_data in selected_matches_from_llm_data:
            try:
                selected_matches_from_llm.append(
                    LLMSelectedFixtureResponse(**item_data)
                )
            except Exception as e:  # Catch Pydantic validation error or other issues
                print(
                    f"Warning: Skipping item due to validation error: {item_data}, Error: {e}"
                )
                continue  # Skip malformed items

    except Exception as e:
        # This catches errors from the Gemini API call itself or initial parsing
        print(
            f"ERROR: Exception during Gemini API call or processing for user {user_id}: {str(e)}"
        )
        # Log the full prompt if an error occurs during API call
        error_prompt_log = (
            full_llm_prompt
            if "full_llm_prompt" in locals()
            else "Prompt not generated."
        )
        print(
            f"LLM Prompt that may have caused error (first 1000 chars): {error_prompt_log[:1000]}"
        )
        raise HTTPException(
            status_code=500, detail=f"Error interacting with LLM: {str(e)}"
        )

    # 6. Store the generated reminder instructions in Firestore
    reminders_created_count = 0
    if selected_matches_from_llm:
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
            for old_reminder_snap in existing_reminders_query:
                delete_batch.delete(old_reminder_snap.reference)
                deleted_old_count += 1
                if deleted_old_count % 490 == 0:  # Commit batch if it gets large
                    delete_batch.commit()
                    delete_batch = db.batch()
            if (
                deleted_old_count % 490 != 0 and deleted_old_count > 0
            ):  # commit remaining
                delete_batch.commit()
            print(
                f"Deleted {deleted_old_count} old pending reminders for user {user_id} for the processed fixtures."
            )

        # Now, create new reminders from LLM output
        batch = db.batch()
        items_in_batch = 0
        created_at = datetime.datetime.now(datetime.timezone.utc)

        for llm_match_info in selected_matches_from_llm:
            original_fixture = original_fixtures_map.get(llm_match_info.fixture_id)
            if not original_fixture:
                print(
                    f"Warning: LLM returned fixture_id {llm_match_info.fixture_id} not found in original fixtures. Skipping."
                )
                continue

            kickoff_time_utc = original_fixture.get("match_datetime_utc")
            if not isinstance(kickoff_time_utc, datetime.datetime):
                print(
                    f"Warning: Fixture {llm_match_info.fixture_id} has invalid kickoff_time_utc. Skipping."
                )
                continue  # Should be a datetime object from Firestore

            for trigger in llm_match_info.reminder_triggers:
                reminder_id = str(uuid.uuid4())
                actual_reminder_time = kickoff_time_utc - datetime.timedelta(
                    minutes=trigger.reminder_offset_minutes_before_kickoff
                )

                reminder_doc = {
                    "reminder_id": reminder_id,
                    "user_id": user_id,
                    "fixture_id": llm_match_info.fixture_id,
                    "importance_score": llm_match_info.importance_score,
                    "kickoff_time_utc": kickoff_time_utc,
                    "reminder_offset_minutes_before_kickoff": trigger.reminder_offset_minutes_before_kickoff,
                    "reminder_mode": trigger.reminder_mode,
                    "custom_message": trigger.custom_message,
                    "actual_reminder_time_utc": actual_reminder_time,
                    "status": "pending",
                    "llm_prompt_used_brief": full_llm_prompt[:500]
                    + "...",  # Store a brief version or hash
                    # "llm_response_raw": llm_response_raw, # Be careful storing large raw responses
                    "created_at": created_at,
                    "updated_at": created_at,
                }
                doc_ref = db.collection(REMINDERS_COLLECTION).document(reminder_id)
                batch.set(doc_ref, reminder_doc)
                reminders_created_count += 1
                items_in_batch += 1
                if items_in_batch >= 490:
                    batch.commit()
                    batch = db.batch()
                    items_in_batch = 0

        if items_in_batch > 0:
            batch.commit()

    return {
        "message": f"Scout processing complete for user {user_id}.",
        "user_id": user_id,
        "fixtures_analyzed_count": len(upcoming_fixtures_for_llm),
        "matches_selected_by_llm": len(selected_matches_from_llm),
        "reminders_created": reminders_created_count,
        "raw_llm_output_sample": llm_response_raw[:200]
        + "...",  # Sample for quick check
    }


@app.get("/")
async def read_root():
    return {"message": "Welcome to the Fixture Scout AI - Scout Service"}
