# scout_service/app/models.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import datetime

# --- Pydantic Models for Data Structures ---


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


# --- Firestore Document Models (Optional, but can be useful for clarity) ---
# These aren't strictly Pydantic models for API I/O, but represent DB structure


class UserPreferenceDoc(BaseModel):
    user_id: str
    llm_prompt: Optional[str] = None
    optimized_llm_prompt: str
    # ... other fields if any


class FixtureDoc(BaseModel):  # A simplified version of what we expect from DB
    fixture_id: str
    home_team: Dict[str, str]  # e.g. {"id": "xyz", "name": "Real Madrid"}
    away_team: Dict[str, str]
    league_name: str
    match_datetime_utc: datetime.datetime
    stage: Optional[str] = None
    raw_metadata_blob: Optional[Dict[str, Any]] = None
    # ... other fields


class ReminderDoc(BaseModel):  # What we store in the Reminders collection
    reminder_id: str
    user_id: str
    fixture_id: str
    reason_for_selection: str
    importance_score: int
    kickoff_time_utc: datetime.datetime
    reminder_offset_minutes_before_kickoff: int
    reminder_mode: str
    custom_message: str
    actual_reminder_time_utc: datetime.datetime
    status: str = "pending"
    llm_prompt_used_brief: str
    llm_response_snippet: str
    optimized_llm_prompt_snapshot: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


# Make sure FixtureDoc is defined here if reminder_processing_service.py uses it for original_fixtures_map.
# It should be:
# class FixtureDoc(BaseModel):
#     fixture_id: str
#     home_team: Dict[str, str]
#     away_team: Dict[str, str]
#     league_name: str
#     match_datetime_utc: datetime.datetime
#     stage: Optional[str] = None
#     raw_metadata_blob: Optional[Dict[str, Any]] = None


# --- NEW Models for Feedback Loop ---
class FixtureSnapshotForScout(BaseModel):  # Mirrored from user_management_service
    fixture_id: str
    home_team_name: str
    away_team_name: str
    league_name: str
    match_datetime_utc_iso: str  # Stored as ISO string by User Mgt Service
    stage: Optional[str] = None


class ScoutUserFeedbackDoc(BaseModel):  # For reading from 'user_feedback' collection
    feedback_id: str
    user_id: str
    # reminder_id: str # Not strictly needed by scout for prompt, but part of doc
    # fixture_id: str  # Included in fixture_details_snapshot
    # is_interested: bool # We only fetch is_interested == False
    feedback_reason_text: Optional[str] = None
    fixture_details_snapshot: FixtureSnapshotForScout  # This is the critical context
    original_llm_prompt_snapshot: Optional[str] = (
        None  # The prompt that led to this "bad" reminder
    )
    timestamp: datetime.datetime
