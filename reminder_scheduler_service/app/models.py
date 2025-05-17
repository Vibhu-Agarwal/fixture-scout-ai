# reminder_scheduler_service/app/models.py
from pydantic import BaseModel, EmailStr, ValidationError # Added ValidationError
from typing import Optional, Dict, Any
import datetime

class ReminderDocFromDB(BaseModel):
    reminder_id: str
    user_id: str
    fixture_id: str
    # reason_for_selection: Optional[str] = None # Not strictly needed by scheduler but good to model if present
    # importance_score: Optional[int] = None     # Not strictly needed by scheduler
    kickoff_time_utc: datetime.datetime
    # reminder_offset_minutes_before_kickoff: int # Not strictly needed after actual_reminder_time_utc is calculated
    reminder_mode: str
    custom_message: str
    actual_reminder_time_utc: datetime.datetime
    status: str
    # llm_prompt_used_brief: Optional[str] = None
    # llm_response_snippet: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    # Add any other fields that might be in the ReminderDoc

class UserDocFromDB(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    phone_number: Optional[str] = None
    # created_at: datetime.datetime # Not strictly needed by scheduler