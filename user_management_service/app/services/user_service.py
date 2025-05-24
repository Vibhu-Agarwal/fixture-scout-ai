# user_management_service/app/services/user_service.py
import logging
import datetime

from google.cloud import firestore

from ..config import settings
from ..models import (
    UserResponse,
    UserPreferenceSubmitRequest,
    UserPreferenceResponse,
    UserFeedbackCreateRequest,
    UserFeedbackDoc,
    FixtureSnapshot,
    ReminderDocInternal as UserMgtReminderDocInternal,  # Use a specific alias if needed
)
from pydantic import ValidationError

from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import (
    FirebaseError,
)


logger = logging.getLogger(__name__)


class UserServiceError(Exception):
    pass


class UserNotFoundError(UserServiceError):
    pass


class PreferenceNotFoundError(UserServiceError):
    pass


class GoogleSignInError(UserServiceError):
    pass


class FirebaseAuthError(UserServiceError):
    pass


async def set_user_preferences(
    db: firestore.Client, user_id: str, preference_data: UserPreferenceSubmitRequest
) -> UserPreferenceResponse:
    user_doc_ref = db.collection(settings.USERS_COLLECTION).document(user_id)
    if not user_doc_ref.get().exists:
        logger.warning(f"Attempt to set preferences for non-existent user: {user_id}")
        raise UserNotFoundError(f"User with ID {user_id} not found.")

    # Determine the prompt to be used by the Scout Service
    # This is the core logic incorporating your requirement.
    prompt_to_save_for_scout = ""  # Default to empty if nothing suitable is found
    if preference_data.prompt_for_scout and preference_data.prompt_for_scout.strip():
        prompt_to_save_for_scout = preference_data.prompt_for_scout
        logger.info(f"User {user_id}: Using provided 'prompt_for_scout'.")
    elif preference_data.raw_user_prompt and preference_data.raw_user_prompt.strip():
        prompt_to_save_for_scout = preference_data.raw_user_prompt
        logger.info(
            f"User {user_id}: 'prompt_for_scout' was empty/None, falling back to 'raw_user_prompt'."
        )
    else:
        logger.warning(
            f"User {user_id}: Both 'prompt_for_scout' and 'raw_user_prompt' are empty/None. Saving an empty 'optimized_llm_prompt'."
        )
        # Consider if an empty prompt for scout service is acceptable or if an error should be raised.

    preference_doc_ref = db.collection(settings.USER_PREFERENCES_COLLECTION).document(
        user_id
    )
    updated_at = datetime.datetime.now(datetime.timezone.utc)

    preference_record_to_store = {
        "user_id": user_id,  # Good to have for queries, though doc ID is user_id
        "raw_user_prompt": (
            preference_data.raw_user_prompt if preference_data.raw_user_prompt else ""
        ),  # Store raw, ensure it's at least an empty string
        "optimized_llm_prompt": prompt_to_save_for_scout,  # This is what Scout Service uses
        "updated_at": updated_at,
        # Add any other preference fields here if they are part of UserPreferenceSubmitRequest
    }

    # Using set with merge=True is good if you add more preference fields later
    # and don't want to overwrite them if they are not in the current request.
    preference_doc_ref.set(preference_record_to_store, merge=True)
    logger.info(
        f"Preferences set/updated for user: {user_id}. Scout prompt length: {len(prompt_to_save_for_scout)}"
    )

    return UserPreferenceResponse(**preference_record_to_store)


async def get_user_preferences_from_db(
    db: firestore.Client, user_id: str
) -> UserPreferenceResponse:
    preference_doc_ref = db.collection(settings.USER_PREFERENCES_COLLECTION).document(
        user_id
    )
    preference_doc_snap = preference_doc_ref.get()

    if not preference_doc_snap.exists:
        logger.warning(f"Preferences not found for user: {user_id}")
        raise PreferenceNotFoundError(f"Preferences for user ID {user_id} not found.")

    preference_data = preference_doc_snap.to_dict()
    logger.info(f"Preferences retrieved for user: {user_id}")

    return UserPreferenceResponse(**preference_data)


class FeedbackSubmissionError(UserServiceError):
    pass


async def store_user_feedback(
    db: firestore.Client,
    user_id: str,
    reminder_id: str,
    feedback_data: UserFeedbackCreateRequest,
) -> UserFeedbackDoc:
    logger.info(f"Storing feedback for user_id: {user_id}, reminder_id: {reminder_id}")

    # 1. Fetch the original reminder to get fixture_id and original_llm_prompt_snapshot
    reminder_doc_ref = db.collection(settings.REMINDERS_COLLECTION).document(
        reminder_id
    )
    reminder_snap = reminder_doc_ref.get()
    if not reminder_snap.exists:
        logger.error(
            f"Reminder {reminder_id} not found when trying to store feedback for user {user_id}."
        )
        raise FeedbackSubmissionError(f"Original reminder {reminder_id} not found.")

    try:
        # Use ReminderDocInternal from this service's models if it matches structure,
        # or define a minimal one just for fetching these fields.
        # Assuming ReminderDocInternal from models.py has the necessary fields.
        reminder_details = UserMgtReminderDocInternal(**reminder_snap.to_dict())
        if reminder_details.user_id != user_id:  # Security check
            logger.error(
                f"User {user_id} attempting to submit feedback for reminder {reminder_id} belonging to another user."
            )
            raise FeedbackSubmissionError("Feedback submission forbidden.")
    except ValidationError as e:
        logger.error(
            f"Invalid reminder data for {reminder_id} when fetching for feedback: {e}"
        )
        raise FeedbackSubmissionError(f"Could not process original reminder data: {e}")

    # 2. Fetch fixture details for the snapshot
    fixture_doc_ref = db.collection(settings.FIXTURES_COLLECTION).document(
        reminder_details.fixture_id
    )
    fixture_snap = fixture_doc_ref.get()
    if not fixture_snap.exists:
        logger.error(
            f"Fixture {reminder_details.fixture_id} not found for reminder {reminder_id} during feedback submission."
        )
        # Still proceed with feedback, but snapshot will be minimal or indicate missing
        fixture_snapshot = FixtureSnapshot(
            fixture_id=reminder_details.fixture_id,
            home_team_name="N/A (Original Fixture Not Found)",
            away_team_name="N/A",
            league_name="N/A",
            match_datetime_utc_iso=datetime.datetime.min.replace(
                tzinfo=datetime.timezone.utc
            ).isoformat(),  # Placeholder
            stage="N/A",
        )
    else:
        try:
            fixture_data = fixture_snap.to_dict()
            # Assuming FixtureDocInternal has the right structure from models.py
            from ..models import (
                FixtureDocInternal as UserMgtFixtureDocInternal,
            )  # Alias if needed

            fixture_internal = UserMgtFixtureDocInternal(**fixture_data)
            fixture_snapshot = FixtureSnapshot(
                fixture_id=fixture_internal.fixture_id,
                home_team_name=fixture_internal.home_team.get("name", "N/A"),
                away_team_name=fixture_internal.away_team.get("name", "N/A"),
                league_name=fixture_internal.league_name,
                match_datetime_utc_iso=fixture_internal.match_datetime_utc.isoformat(),
                stage=fixture_internal.stage,
            )
        except ValidationError as e:
            logger.error(
                f"Invalid fixture data {reminder_details.fixture_id} for feedback: {e}"
            )
            # Fallback snapshot
            fixture_snapshot = FixtureSnapshot(
                fixture_id=reminder_details.fixture_id,
                home_team_name="N/A (Fixture Data Invalid)",
                away_team_name="N/A",
                league_name="N/A",
                match_datetime_utc_iso=datetime.datetime.min.replace(
                    tzinfo=datetime.timezone.utc
                ).isoformat(),
                stage="N/A",
            )

    # 3. Create and store the feedback document
    feedback_doc_data = UserFeedbackDoc(
        user_id=user_id,
        reminder_id=reminder_id,
        fixture_id=reminder_details.fixture_id,
        feedback_reason_text=feedback_data.feedback_reason_text,
        fixture_details_snapshot=fixture_snapshot,
        original_llm_prompt_snapshot=getattr(
            reminder_details, "optimized_llm_prompt_snapshot", None
        ),
    )

    feedback_doc_ref = db.collection(settings.USER_FEEDBACK_COLLECTION).document(
        feedback_doc_data.feedback_id
    )
    feedback_doc_ref.set(feedback_doc_data.model_dump())

    logger.info(
        f"Feedback stored successfully: {feedback_doc_data.feedback_id} for user {user_id}, reminder {reminder_id}"
    )
    return feedback_doc_data


async def get_or_create_user_profile_from_firebase_token(
    db: firestore.Client, firebase_id_token: str
) -> UserResponse:
    """
    Verifies a Firebase ID token, then finds or creates a user profile
    in Firestore using the Firebase UID as the primary key.
    Returns the UserResponse.
    """
    try:
        decoded_token = firebase_auth.verify_id_token(firebase_id_token)
        firebase_uid = decoded_token["uid"]  # This IS our user_id now
        user_email = decoded_token.get("email")
        user_name = decoded_token.get(
            "name",
            user_email.split("@")[0] if user_email else f"User_{firebase_uid[:6]}",
        )
        # picture = decoded_token.get('picture')

        logger.info(
            f"Firebase ID Token verified. User ID (Firebase UID): {firebase_uid}, Email: {user_email}"
        )

        user_doc_ref = db.collection(settings.USERS_COLLECTION).document(
            firebase_uid
        )  # Use Firebase UID as document ID
        user_doc_snap = user_doc_ref.get()

        if user_doc_snap.exists:
            user_data = user_doc_snap.to_dict()
            logger.info(f"User profile found in Firestore for User ID: {firebase_uid}")

            # Optionally update name/email if they changed in Firebase and you want to sync
            updates = {}
            if user_data.get("name") != user_name:
                updates["name"] = user_name
            if user_data.get("email") != user_email:
                updates["email"] = user_email
            if updates:
                updates["updated_at"] = datetime.datetime.now(datetime.timezone.utc)
                user_doc_ref.update(updates)
                # Re-fetch or merge for UserResponse if needed, or assume Pydantic model handles it
                user_data.update(updates)

            # Ensure all fields for UserResponse are present
            return UserResponse(
                user_id=user_data.get("user_id", firebase_uid),
                name=user_data.get("name", user_name),
                email=user_data.get("email", user_email),
                phone_number=user_data.get("phone_number"),
                created_at=user_data.get("created_at"),
            )
        else:
            # User exists in Firebase Auth, but not in our Firestore Users collection yet. Create it.
            created_at = datetime.datetime.now(datetime.timezone.utc)

            new_user_record = {
                "user_id": firebase_uid,  # Firebase UID is the user_id
                "name": user_name,
                "email": user_email,
                "phone_number": None,
                "created_at": created_at,
                "updated_at": created_at,
                "signup_method": "firebase_google",
            }
            user_doc_ref.set(new_user_record)
            logger.info(
                f"New user profile created in Firestore. User ID (Firebase UID): {firebase_uid}"
            )

            return UserResponse(**new_user_record)  # Pydantic will validate

    except FirebaseError as e:
        logger.error(f"Firebase authentication error: {e}", exc_info=True)
        raise FirebaseAuthError(f"Firebase authentication failed: {str(e)}")
    except Exception as e:
        logger.error(
            f"Error processing Firebase token or creating user profile: {e}",
            exc_info=True,
        )
        raise FirebaseAuthError(f"An unexpected error occurred: {str(e)}")
