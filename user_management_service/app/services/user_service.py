# user_management_service/app/services/user_service.py
import logging
import uuid
import datetime
from typing import Optional, Dict, Any

from google.cloud import firestore

from ..config import settings
from ..models import (
    UserSignupRequest,
    UserResponse,
    UserPreferenceSubmitRequest,
    UserPreferenceResponse,
    UserFeedbackCreateRequest,
    UserFeedbackDoc,
    FixtureSnapshot,
    ReminderDocInternal as UserMgtReminderDocInternal,  # Use a specific alias if needed
)
from pydantic import ValidationError

from google.oauth2 import id_token  # For verifying Google ID token
from google.auth.transport import (
    requests as google_auth_requests,
)  # HTTP Abstraction by google-auth
from ..auth_utils import create_access_token

logger = logging.getLogger(__name__)


class UserServiceError(Exception):
    pass


class UserNotFoundError(UserServiceError):
    pass


class PreferenceNotFoundError(UserServiceError):
    pass


class GoogleSignInError(UserServiceError):
    pass


async def create_user(
    db: firestore.Client, user_data: UserSignupRequest
) -> UserResponse:
    user_id = str(uuid.uuid4())
    created_at = datetime.datetime.now(datetime.timezone.utc)
    user_doc_ref = db.collection(settings.USERS_COLLECTION).document(user_id)

    # Basic check for existing email (can be enhanced)
    existing_users = (
        db.collection(settings.USERS_COLLECTION)
        .where("email", "==", user_data.email)
        .limit(1)
        .stream()
    )
    if any(existing_users):
        logger.warning(f"Attempt to create user with existing email: {user_data.email}")
        raise UserServiceError(f"User with email {user_data.email} already exists.")

    user_record = {
        "user_id": user_id,
        "name": user_data.name,
        "email": str(user_data.email),
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


async def process_google_signin(
    db: firestore.Client, token: str
) -> tuple[str, str]:  # Returns (app_jwt, internal_user_id)
    """
    Verifies Google ID token, finds or creates a user, and returns an application JWT.
    """
    if not settings.GOOGLE_CLIENT_ID:
        logger.error("Google Client ID not configured. Cannot verify Google ID Token.")
        raise GoogleSignInError(
            "Authentication service not configured (missing Google Client ID)."
        )

    try:
        # Verify the ID token and get user info
        # The audience should be your Google Client ID.
        idinfo = id_token.verify_oauth2_token(
            token,
            google_auth_requests.Request(),  # HTTP request object for google-auth
            settings.GOOGLE_CLIENT_ID,
        )

        # idinfo contains user data like:
        # idinfo['iss'] == 'accounts.google.com' or 'https://accounts.google.com'
        # idinfo['sub'] -> Google User ID (unique)
        # idinfo['email']
        # idinfo['email_verified']
        # idinfo['name']
        # idinfo['picture'] (URL)
        # ... and more

        if not idinfo.get("email_verified"):
            logger.warning(
                f"Google sign-in attempt with unverified email: {idinfo.get('email')}"
            )
            raise GoogleSignInError("Email not verified by Google.")

        google_user_id = idinfo["sub"]
        user_email = idinfo["email"]
        user_name = idinfo.get("name", user_email.split("@")[0])  # Fallback for name

        # Check if user exists by Google User ID
        users_ref = db.collection(settings.USERS_COLLECTION)
        query = users_ref.where("google_id", "==", google_user_id).limit(1).stream()

        user_doc_snap = None
        for doc in query:  # Should be at most one
            user_doc_snap = doc
            break

        internal_user_id = None
        user_created_now = False

        if user_doc_snap and user_doc_snap.exists:
            user_data = user_doc_snap.to_dict()
            internal_user_id = user_data.get("user_id")
            logger.info(
                f"Google Sign-In: User found by google_id {google_user_id}. Internal user_id: {internal_user_id}"
            )
            # Optionally update user's name/picture from Google if they changed
            if user_data.get("name") != user_name:  # Example update
                user_doc_snap.reference.update(
                    {
                        "name": user_name,
                        "updated_at": datetime.datetime.now(datetime.timezone.utc),
                    }
                )
        else:
            # If not found by google_id, try by email (for users who might have signed up via email before Google Sign-In was an option)
            # This part is optional and depends on your user migration strategy.
            # For a new system, you might just create a new user if google_id is not found.
            logger.info(
                f"Google Sign-In: No user found by google_id {google_user_id}. Checking by email {user_email}..."
            )
            query_email = users_ref.where("email", "==", user_email).limit(1).stream()
            email_user_doc_snap = None
            for doc in query_email:
                email_user_doc_snap = doc
                break

            if email_user_doc_snap and email_user_doc_snap.exists:
                # User exists with this email, link Google ID
                user_data = email_user_doc_snap.to_dict()
                internal_user_id = user_data.get("user_id")
                email_user_doc_snap.reference.update(
                    {
                        "google_id": google_user_id,
                        "name": user_name,  # Update name if different
                        "updated_at": datetime.datetime.now(datetime.timezone.utc),
                    }
                )
                logger.info(
                    f"Google Sign-In: User found by email {user_email}, linked google_id {google_user_id}. Internal user_id: {internal_user_id}"
                )
            else:
                # User does not exist, create new user
                internal_user_id = str(uuid.uuid4())
                created_at = datetime.datetime.now(datetime.timezone.utc)
                new_user_record = {
                    "user_id": internal_user_id,
                    "google_id": google_user_id,  # Store the Google User ID
                    "name": user_name,
                    "email": user_email,
                    "phone_number": None,  # No phone from Google Sign-In directly
                    "created_at": created_at,
                    "updated_at": created_at,
                    "signup_method": "google",  # Optional: track signup method
                }
                users_ref.document(internal_user_id).set(new_user_record)
                user_created_now = True
                logger.info(
                    f"Google Sign-In: New user created. Internal user_id: {internal_user_id}, Email: {user_email}"
                )

        if not internal_user_id:  # Should not happen if logic above is correct
            raise GoogleSignInError("Failed to retrieve or create user internal ID.")

        # Create application JWT
        # The 'sub' (subject) claim is standard for user ID in JWT.
        # Or you can use a custom claim like 'user_id'.
        access_token_data = {"sub": internal_user_id, "email": user_email}
        # You could add 'name': user_name if needed in token, but keep tokens small
        app_jwt = create_access_token(data=access_token_data)

        return app_jwt, internal_user_id

    except ValueError as e:
        logger.error(f"Invalid Google ID Token: {e}", exc_info=True)
        raise GoogleSignInError(f"Invalid Google ID Token: {e}")
    except Exception as e:
        logger.error(f"Error during Google sign-in processing: {e}", exc_info=True)
        raise GoogleSignInError(
            f"An unexpected error occurred during Google sign-in: {str(e)}"
        )
