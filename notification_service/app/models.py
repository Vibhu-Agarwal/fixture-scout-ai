# notification_service/app/models.py
import uuid
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
import datetime
import base64
import json


class PubSubMessageData(BaseModel):  # The actual payload decoded from Pub/Sub message
    original_reminder_id: str
    user_id: str
    fixture_id: str
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    message_content: str
    reminder_mode: str  # "email", "phone_call_mock"
    kickoff_time_utc: Optional[str] = None  # ISO format string


class PubSubMessage(BaseModel):  # Structure of the message pushed by Pub/Sub
    message: Dict[str, Any]  # Contains 'data', 'messageId', 'attributes', etc.
    subscription: str

    def get_payload(self) -> PubSubMessageData:
        """Decodes the base64 data from Pub/Sub message."""
        try:
            base64_data = self.message.get("data")
            if not base64_data:
                raise ValueError("No 'data' field in Pub/Sub message.")
            decoded_data_str = base64.b64decode(base64_data).decode("utf-8")
            payload_dict = json.loads(decoded_data_str)
            return PubSubMessageData(**payload_dict)
        except Exception as e:
            raise ValueError(f"Error decoding Pub/Sub message data: {e}")


class NotificationLogDoc(BaseModel):
    notification_log_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())
    )  # Auto-generate
    original_reminder_id: str
    user_id: str
    reminder_mode: str
    status: str  # e.g., "processing", "sent_mock", "failed_mock_error", "failed_invalid_payload"
    attempt_count: int = 1
    contact_target: Optional[str] = None  # e.g., email address or phone number
    message_content_snippet: str
    last_attempt_utc: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    processed_at: Optional[datetime.datetime] = None
    final_status_published_at: Optional[datetime.datetime] = (
        None  # When status was sent to status topic
    )
    error_message: Optional[str] = None
    # provider_message_id: Optional[str] = None # For real providers
