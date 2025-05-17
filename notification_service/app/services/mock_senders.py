# notification_service/app/services/mock_senders.py
import logging
from typing import Protocol, Dict, Any
from ..models import PubSubMessageData  # Assuming this has the necessary details

logger = logging.getLogger(__name__)


class INotificationSender(Protocol):
    async def send(
        self, payload: PubSubMessageData
    ) -> tuple[bool, str]:  # (success, status_message)
        ...


class MockEmailSender:
    async def send(self, payload: PubSubMessageData) -> tuple[bool, str]:
        if not payload.contact_email:
            logger.error(
                f"MOCK EMAIL: No email address for user {payload.user_id}, reminder {payload.original_reminder_id}"
            )
            return False, "failed_no_email_address"

        log_message = f"MOCK EMAIL to {payload.contact_email}: '{payload.message_content}' (ReminderID: {payload.original_reminder_id})"
        print(log_message)  # For easy local visibility
        logger.info(log_message)
        # Simulate some potential for failure if needed for testing
        # import random
        # if random.random() < 0.1: # 10% chance of "failure"
        #     logger.warning(f"MOCK EMAIL: Simulated provider failure for {payload.contact_email}")
        #     return False, "failed_mock_provider_error"
        return True, "sent_mock_email"


class MockPhoneCallSender:
    async def send(self, payload: PubSubMessageData) -> tuple[bool, str]:
        if not payload.contact_phone:
            logger.error(
                f"MOCK PHONE: No phone number for user {payload.user_id}, reminder {payload.original_reminder_id}"
            )
            return False, "failed_no_phone_number"

        log_message = f"MOCK PHONE CALL to {payload.contact_phone}: Triggering call with message hint '{payload.message_content[:50]}...' (ReminderID: {payload.original_reminder_id})"
        print(log_message)
        logger.info(log_message)
        return True, "sent_mock_phone_call"


# Factory or dispatcher to get the right sender
def get_sender(mode: str) -> INotificationSender:
    if mode == "email":
        return MockEmailSender()
    elif mode == "phone_call_mock":
        return MockPhoneCallSender()
    else:
        logger.error(f"Unsupported notification mode: {mode}")
        raise ValueError(f"Unsupported notification mode: {mode}")
