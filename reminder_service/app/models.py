# reminder_service/app/models.py
from pydantic import BaseModel, EmailStr, Field  # Added Field
from typing import Optional, Dict, Any
import datetime
import base64  # For PubSubMessage decoding
import json  # For PubSubMessage decoding


# --- Models for Scheduler Logic ---
class ReminderDocFromDB(BaseModel):
    reminder_id: str
    user_id: str
    fixture_id: str
    kickoff_time_utc: datetime.datetime
    reminder_mode: str
    custom_message: str
    actual_reminder_time_utc: datetime.datetime
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    # Add other optional fields that might be present to avoid validation errors if they exist
    published_to_topic: Optional[str] = None
    reason_for_selection: Optional[str] = None
    importance_score: Optional[int] = None
    llm_prompt_used_brief: Optional[str] = None
    llm_response_snippet: Optional[str] = None
    error_detail: Optional[str] = None  # If status is error_validation etc.
    last_triggered_attempt_utc: Optional[datetime.datetime] = None


class UserDocFromDB(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    phone_number: Optional[str] = None


# --- Models for Status Updater Logic ---
class NotificationStatusUpdatePayload(
    BaseModel
):  # Payload from notification-status-updates-topic
    original_reminder_id: str
    user_id: str  # For logging/verification
    reminder_mode: str  # For logging/verification
    final_notification_status: str  # e.g., "sent_mock_email", "failed_no_email_address", "delivered_mock" (if we evolve)
    timestamp_utc: str  # ISO format string
    error_detail: Optional[str] = None


class PubSubPushMessage(
    BaseModel
):  # Generic model for incoming Pub/Sub push request body
    message: Dict[str, Any]  # Contains 'data', 'messageId', 'attributes', 'publishTime'
    subscription: str  # Name of the subscription that pushed the message

    def decode_data(self) -> Dict[str, Any]:
        """Decodes the base64 data from Pub/Sub message and parses as JSON."""
        base64_data = self.message.get("data")
        if not base64_data:
            raise ValueError("No 'data' field in Pub/Sub message.")
        decoded_data_str = base64.b64decode(base64_data).decode("utf-8")
        return json.loads(decoded_data_str)
