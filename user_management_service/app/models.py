# user_management_service/app/models.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
import datetime


# --- Existing User and Preference Models ---
class UserSignupRequest(BaseModel):
    name: str = Field(..., examples=["John Doe"])
    email: EmailStr = Field(..., examples=["john.doe@example.com"])
    phone_number: Optional[str] = Field(None, examples=["+15551234567"])


class UserResponse(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    phone_number: Optional[str] = None
    created_at: datetime.datetime


class UserPreferenceSubmitRequest(BaseModel):
    optimized_llm_prompt: str = Field(
        ...,
        examples=[
            "Remind me of all Real Madrid matches and important Champions League games involving top teams."
        ],
    )


class UserPreferenceResponse(BaseModel):
    user_id: str
    optimized_llm_prompt: str
    updated_at: datetime.datetime


# --- New Models for Listing Reminders ---


# Represents a fixture's details, to be embedded in the reminder response
class FixtureInfo(BaseModel):
    fixture_id: str
    home_team_name: str
    away_team_name: str
    league_name: str
    match_datetime_utc: datetime.datetime
    stage: Optional[str] = None


# Represents a single reminder item in the list returned to the user
class UserReminderItem(BaseModel):
    reminder_id: str
    fixture_details: FixtureInfo  # Embed fixture details
    importance_score: int
    custom_message: str  # The message for the *next* or a primary reminder trigger
    reminder_mode: str  # Mode of the *next* or primary reminder trigger
    actual_reminder_time_utc: datetime.datetime  # Time of the *next* reminder trigger
    current_status: str  # Status from the Reminders collection (e.g., "pending", "queued_for_notification", "sent")
    kickoff_time_utc: datetime.datetime


class UserRemindersListResponse(BaseModel):
    user_id: str
    reminders: List[UserReminderItem]
    count: int


# --- Pydantic models for Firestore documents (internal use) ---
# These help in parsing data read from Firestore within services
class ReminderDocInternal(BaseModel):  # Model for data read from 'reminders' collection
    reminder_id: str
    user_id: str
    fixture_id: str
    importance_score: int  # This was likely from the overall match importance
    kickoff_time_utc: datetime.datetime

    # Fields for the specific trigger represented by this document
    reminder_offset_minutes_before_kickoff: int
    reminder_mode: str
    custom_message: str
    actual_reminder_time_utc: (
        datetime.datetime
    )  # This is the key time for this specific reminder doc

    status: str  # current status of this specific reminder trigger

    # Optional fields that might be present from Scout Service
    reason_for_selection: Optional[str] = None  # This is per-match, so it's fine here
    llm_prompt_used_brief: Optional[str] = None
    llm_response_snippet: Optional[str] = None
    published_to_topic: Optional[str] = None  # From reminder_service after queueing
    last_notification_outcome: Optional[str] = (
        None  # From reminder_service after status update
    )
    last_notification_error_detail: Optional[str] = None
    last_notification_outcome_at_utc: Optional[datetime.datetime] = None

    created_at: datetime.datetime
    updated_at: datetime.datetime


class FixtureDocInternal(BaseModel):  # Model for data read from 'fixtures' collection
    fixture_id: str
    home_team: Dict[str, str]  # e.g. {"name": "Team A", "id": "team_a_id"}
    away_team: Dict[str, str]
    league_name: str
    match_datetime_utc: datetime.datetime
    stage: Optional[str] = None
    # ... any other fields
