# user_management_service/app/main.py
import base64
import json
import logging
from fastapi import (
    FastAPI,
    HTTPException,
    Body,
    Path,
    Depends,
    status as http_status,
    Header,
)
from fastapi.security import (
    OAuth2PasswordBearer,
)  # For Bearer token in Authorization header
from contextlib import asynccontextmanager
from typing import List, Annotated

# Setup logging first
from .utils.logging_config import setup_logging

setup_logging()

from .config import settings
from .firestore_client import get_firestore_client
from .models import (
    FirebaseIdTokenRequest,
    UserResponse,
    UserPreferenceSubmitRequest,
    UserPreferenceResponse,
    UserRemindersListResponse,
    UserReminderItem,
    TokenData,
    UserFeedbackCreateRequest,
    UserFeedbackDoc,
)
from .services.user_service import (
    get_or_create_user_profile_from_firebase_token,
    store_user_feedback,
    set_user_preferences,
    get_user_preferences_from_db,
    UserNotFoundError,
    PreferenceNotFoundError,
    FeedbackSubmissionError,
)
from .services.reminder_query_service import (
    get_user_reminders,
    ReminderQueryError,
)
from .firebase_admin_init import initialize_firebase_admin
from firebase_admin import auth as firebase_auth, exceptions as firebase_exceptions

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

logger = logging.getLogger(__name__)


async def get_current_user(
    x_endpoint_api_userinfo: Annotated[
        str | None, Header(convert_underscores=True)
    ] = None,
) -> TokenData:
    """
    Dependency to get user information passed by the ESPv2 gateway
    in the X-Endpoint-API-UserInfo header after Firebase Auth validation.
    """
    credentials_exception = HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED,
        detail="User not authenticated by API Gateway",
    )
    if x_endpoint_api_userinfo is None:
        logger.warning(
            "X-Endpoint-API-UserInfo header missing from request (ESPv2 should provide this)."
        )
        raise credentials_exception

    try:
        decoded_userinfo_str = x_endpoint_api_userinfo

        # Calculate required padding
        missing_padding = len(decoded_userinfo_str) % 4
        if missing_padding:
            decoded_userinfo_str += "=" * (4 - missing_padding)
            logger.debug(
                f"Added padding to X-Endpoint-API-UserInfo. Original length: {len(x_endpoint_api_userinfo)}, New length: {len(decoded_userinfo_str)}"
            )

        userinfo_json_bytes = base64.urlsafe_b64decode(decoded_userinfo_str)
        userinfo_json_str = userinfo_json_bytes.decode("utf-8")
        userinfo = json.loads(userinfo_json_str)

        # ESPv2 passes Firebase UID in 'id' field, email in 'email' field.
        # (Verify the exact field names ESPv2 uses for Firebase claims)
        # Common claims passed by ESPv2 after Firebase Auth: 'id' (Firebase UID), 'email', 'issuer'.
        firebase_uid = userinfo.get("user_id")
        email = userinfo.get("email")

        if not firebase_uid:
            logger.error(
                f"Firebase UID ('id' or 'user_id') not found in X-Endpoint-API-UserInfo: {userinfo}"
            )
            raise credentials_exception

        logger.debug(f"Authenticated user from Gateway (Firebase UID): {firebase_uid}")

        return TokenData(user_id=firebase_uid)
    except Exception as e:
        logger.error(
            f"Error decoding/parsing X-Endpoint-API-UserInfo header: {e}", exc_info=True
        )
        raise credentials_exception


# --- Lifespan Event Handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("User Management & Preference Service starting up...")
    try:
        get_firestore_client()  # Initialize Firestore client
        initialize_firebase_admin()  # Ensure Firebase Admin SDK is initialized
        logger.info("UserMgt Firestore client initialized successfully on startup.")
    except Exception as e:
        logger.critical(
            f"UserMgt: Failed to initialize Firestore client on startup: {e}",
            exc_info=True,
        )
    yield
    logger.info("User Management & Preference Service shutting down...")


app = FastAPI(
    title="User Management & Preference Service",
    description="Manages user signups, preferences, authentication, and lists their reminders.",
    version="0.4.0",
    lifespan=lifespan,
)


# This endpoint now primarily ensures user profile exists in your DB after Firebase client-side login.
# It could return the UserResponse from your DB.
@app.post("/auth/firebase/ensure-profile", response_model=UserResponse)
async def api_ensure_firebase_user_profile(
    request_data: FirebaseIdTokenRequest = Body(...),
):
    """
    Receives Firebase ID Token from client (after client-side Firebase Google Sign-In).
    Verifies token, ensures user profile exists in local DB, returns local user profile.
    No application-specific JWT is issued here; client uses Firebase ID Token for API calls.
    """
    try:
        db = get_firestore_client()
        user_profile = await get_or_create_user_profile_from_firebase_token(
            db, request_data.firebase_id_token
        )
        return user_profile
    except firebase_exceptions.FirebaseError as e:
        logger.error(f"Firebase ensure profile failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during ensure profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error.",
        )


@app.put("/preferences", response_model=UserPreferenceResponse)
async def api_submit_user_preferences(
    preference_data: UserPreferenceSubmitRequest = Body(...),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Allows an authenticated user to submit or update their LLM prompt preference.
    """
    try:
        db = get_firestore_client()
        # Use current_user.user_id from the validated token
        updated_preference = await set_user_preferences(
            db, current_user.user_id, preference_data
        )
        return updated_preference
    # UserNotFoundError might not be directly applicable if user_id is from token,
    # but set_user_preferences could still internally check or have issues.
    except UserNotFoundError as e:  # Should be rare if token is valid and user exists
        logger.error(
            f"Set preferences failed, user from token not found (should not happen): {current_user.user_id}, error: {e}"
        )
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="User associated with token not found.",
        )
    except Exception as e:
        logger.error(
            f"Unexpected error setting preferences for user {current_user.user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while setting preferences.",
        )


@app.get("/preferences", response_model=UserPreferenceResponse)
async def api_get_user_preferences(
    current_user: TokenData = Depends(get_current_user),
):
    """
    Retrieves an authenticated user's LLM prompt preference.
    """
    try:
        db = get_firestore_client()
        preferences = await get_user_preferences_from_db(db, current_user.user_id)
        return preferences
    except PreferenceNotFoundError as e:
        logger.warning(
            f"Get preferences failed, not found for user: {current_user.user_id}"
        )
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error getting preferences for user {current_user.user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while getting preferences.",
        )


@app.get("/reminders", response_model=UserRemindersListResponse)
async def api_get_user_reminders(
    current_user: TokenData = Depends(get_current_user),
):
    """
    Retrieves a list of all upcoming reminders for the authenticated user.
    """
    try:
        db = get_firestore_client()
        reminders_list: List[UserReminderItem] = await get_user_reminders(
            db, current_user.user_id
        )
        return UserRemindersListResponse(
            user_id=current_user.user_id,
            reminders=reminders_list,
            count=len(reminders_list),
        )
    except ReminderQueryError as e:
        logger.error(
            f"Error querying reminders for user {current_user.user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve reminders: {str(e)}",
        )
    except Exception as e:
        logger.error(
            f"Unexpected error fetching reminders for user {current_user.user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred while fetching reminders.",
        )


@app.post(
    "/reminders/{reminder_id}/feedback", response_model=UserFeedbackDoc, status_code=201
)
async def api_submit_reminder_feedback(
    reminder_id: str = Path(
        ..., description="The ID of the reminder this feedback is for"
    ),
    feedback_payload: UserFeedbackCreateRequest = Body(...),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Allows an authenticated user to submit feedback for a specific reminder.
    """
    try:
        db = get_firestore_client()
        # The store_user_feedback function should internally verify that current_user.user_id
        # is associated with the reminder_id or the user it belongs to.
        feedback_doc = await store_user_feedback(
            db, current_user.user_id, reminder_id, feedback_payload
        )
        return feedback_doc
    except FeedbackSubmissionError as e:
        logger.warning(
            f"Feedback submission failed for user {current_user.user_id}, reminder {reminder_id}: {e}"
        )
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e)
            )
        elif "forbidden" in str(e).lower():  # If store_user_feedback checks ownership
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN, detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e)
            )
    except Exception as e:
        logger.error(
            f"Unexpected error submitting feedback for user {current_user.user_id}, reminder {reminder_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred.",
        )


@app.get("/")
async def read_root():
    return {
        "message": "Welcome to the Fixture Scout AI - User Management & Preference Service"
    }


@app.get("/health")
async def health_check():
    db_ok = False
    try:
        get_firestore_client()
        db_ok = True
    except Exception:
        logger.warning(
            "Health check: Firestore client not healthy for UserMgt service."
        )

    if db_ok:
        return {"status": "ok", "firestore_healthy": True}
    else:
        return {
            "status": "degraded",
            "firestore_healthy": False,
            "detail": "Firestore client issue.",
        }
