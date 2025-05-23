# user_management_service/app/models.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
import datetime


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
    # User's directly entered prompt
    raw_user_prompt: Optional[str] = Field(
        None,  # Allow it to be None if user clears it or on initial setup
        examples=["I like Real Madrid and big CL games, especially finals."],
        description="User's natural language prompt for match preferences.",
    )
    # This is the prompt that the UI gets back from PromptOptimizationService
    # and then sends here when the user saves their preferences.
    # It could be the same as raw_user_prompt if optimization wasn't used or user preferred their own.
    # Or it could be what the UI decided to send after user interaction with optimizer.
    # Let's call it what it effectively is: the prompt to be used by the Scout service.
    prompt_for_scout: Optional[str] = Field(
        None,  # Allow it to be None
        examples=[
            "All Real Madrid matches. Key Champions League matches involving top-tier European clubs, especially during knockout stages..."
        ],
        description="The prompt (raw or optimized) that will be saved for the Scout service.",
    )


class UserPreferenceResponse(BaseModel):
    user_id: str
    raw_user_prompt: Optional[str] = None  # Now returning the raw prompt as well
    optimized_llm_prompt: Optional[str] = None  # This is what Scout service uses
    updated_at: datetime.datetime
    # other preferences can be added here


# --- New Models for Listing Reminders ---


# Represents a fixture's details, to be embedded in the reminder response
class FixtureInfo(BaseModel):
    fixture_id: str
    home_team_name: str
    away_team_name: str
    league_name: str
    match_datetime_utc: datetime.datetime
    stage: Optional[str] = None


class UserReminderItem(BaseModel):
    # ... (as before) ...
    reminder_id: str
    fixture_details: FixtureInfo
    importance_score: int
    custom_message: str
    reminder_mode: str
    actual_reminder_time_utc: datetime.datetime
    current_status: str
    kickoff_time_utc: datetime.datetime


class UserRemindersListResponse(BaseModel):
    # ... (as before) ...
    user_id: str
    reminders: List[UserReminderItem]
    count: int


# --- Pydantic models for Firestore documents (Remain the same) ---
class ReminderDocInternal(BaseModel):
    # ... (as before) ...
    reminder_id: str
    user_id: str
    fixture_id: str
    importance_score: int
    kickoff_time_utc: datetime.datetime
    reminder_offset_minutes_before_kickoff: int
    reminder_mode: str
    custom_message: str
    actual_reminder_time_utc: datetime.datetime
    status: str
    reason_for_selection: Optional[str] = None
    llm_prompt_used_brief: Optional[str] = None
    llm_response_snippet: Optional[str] = None
    published_to_topic: Optional[str] = None
    last_notification_outcome: Optional[str] = None
    last_notification_error_detail: Optional[str] = None
    last_notification_outcome_at_utc: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class FixtureDocInternal(BaseModel):
    fixture_id: str
    home_team: Dict[str, str]
    away_team: Dict[str, str]
    league_name: str
    match_datetime_utc: datetime.datetime
    stage: Optional[str] = None
