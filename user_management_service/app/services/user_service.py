# user_management_service/app/services/user_service.py
import logging
import uuid
import datetime
from typing import Optional

from google.cloud import firestore
from pydantic import EmailStr

from ..config import settings
from ..models import (
    UserSignupRequest,
    UserResponse,
    UserPreferenceSubmitRequest,
    UserPreferenceResponse,
)

logger = logging.getLogger(__name__)


class UserServiceError(Exception):
    pass


class UserNotFoundError(UserServiceError):
    pass


class PreferenceNotFoundError(UserServiceError):
    pass


async def create_user(
    db: firestore.Client, user_data: UserSignupRequest
) -> UserResponse:
    user_id = str(uuid.uuid4())
    created_at = datetime.datetime.now(datetime.timezone.utc)
    user_doc_ref = db.collection(settings.USERS_COLLECTION).document(user_id)

    # Basic check for existing email (can be enhanced)
    # existing_users = db.collection(settings.USERS_COLLECTION).where("email", "==", user_data.email).limit(1).stream()
    # if any(existing_users):
    #     logger.warning(f"Attempt to create user with existing email: {user_data.email}")
    #     raise UserServiceError(f"User with email {user_data.email} already exists.")

    user_record = {
        "user_id": user_id,
        "name": user_data.name,
        "email": user_data.email,
        "phone_number": user_data.phone_number,
        "created_at": created_at,
    }
    user_doc_ref.set(user_record)
    logger.info(f"User created successfully: {user_id}, Email: {user_data.email}")
    return UserResponse(**user_record)


async def set_user_preferences(
    db: firestore.Client, user_id: str, preference_data: UserPreferenceSubmitRequest
) -> UserPreferenceResponse:
    user_doc_ref = db.collection(settings.USERS_COLLECTION).document(user_id)
    if not user_doc_ref.get().exists:
        logger.warning(f"Attempt to set preferences for non-existent user: {user_id}")
        raise UserNotFoundError(f"User with ID {user_id} not found.")

    preference_doc_ref = db.collection(settings.USER_PREFERENCES_COLLECTION).document(
        user_id
    )
    updated_at = datetime.datetime.now(datetime.timezone.utc)
    preference_record = {
        "user_id": user_id,
        "optimized_llm_prompt": preference_data.optimized_llm_prompt,
        "updated_at": updated_at,
    }
    preference_doc_ref.set(preference_record)  # Creates or overwrites
    logger.info(f"Preferences set/updated for user: {user_id}")
    return UserPreferenceResponse(**preference_record)


async def get_user_preferences_from_db(
    db: firestore.Client, user_id: str
) -> UserPreferenceResponse:
    preference_doc_ref = db.collection(settings.USER_PREFERENCES_COLLECTION).document(
        user_id
    )
    preference_doc = preference_doc_ref.get()

    if not preference_doc.exists:
        logger.warning(f"Preferences not found for user: {user_id}")
        raise PreferenceNotFoundError(f"Preferences for user ID {user_id} not found.")

    logger.info(f"Preferences retrieved for user: {user_id}")
    return UserPreferenceResponse(**preference_doc.to_dict())
