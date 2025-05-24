# user_management_service/app/main.py
import logging
from fastapi import (
    FastAPI,
    HTTPException,
    Body,
    Path,
    Depends,
    status as http_status,
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
    UserSignupRequest,
    UserResponse,
    UserPreferenceSubmitRequest,
    UserPreferenceResponse,
    UserRemindersListResponse,
    UserReminderItem,
    TokenData,
    TokenResponse,
    GoogleIdTokenRequest,
    UserFeedbackCreateRequest,
    UserFeedbackDoc,
)
from .services.user_service import (
    store_user_feedback,
    create_user,
    set_user_preferences,
    get_user_preferences_from_db,
    process_google_signin,
    UserServiceError,
    UserNotFoundError,
    PreferenceNotFoundError,
    FeedbackSubmissionError,
    GoogleSignInError,
)
from .services.reminder_query_service import (
    get_user_future_reminders,
    ReminderQueryError,
)
from .auth_utils import (
    decode_access_token,
)

logger = logging.getLogger(__name__)

# --- JWT Authentication Setup ---
# oauth2_scheme defines how to get the token (from Authorization header as Bearer token)
# tokenUrl is not strictly needed here if we don't have a traditional username/password login endpoint
# that issues tokens directly. Our /auth/google/signin will issue tokens.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")  # Placeholder tokenUrl


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenData:
    """
    Dependency to validate JWT and extract user information.
    This will be used by protected endpoints.
    """
    credentials_exception = HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = decode_access_token(token)  # From your auth_utils.py
    if token_data is None or token_data.user_id is None:
        logger.warning(f"Invalid or expired token received.")
        raise credentials_exception

    # You could fetch user from DB here to ensure they exist and are active,
    # but for now, just relying on valid token with user_id claim.
    # user = get_user_from_db(db, user_id=token_data.user_id)
    # if user is None:
    #     raise credentials_exception
    logger.debug(f"Token validated for user_id: {token_data.user_id}")
    return token_data  # Contains user_id (and potentially other claims)


# --- Lifespan Event Handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("User Management & Preference Service starting up...")
    try:
        get_firestore_client()  # Initialize Firestore client
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
    version="0.3.0",  # Incremented version for auth changes
    lifespan=lifespan,
)


@app.post("/auth/google/signin", response_model=TokenResponse)
async def api_google_signin(request_data: GoogleIdTokenRequest = Body(...)):
    """
    Handles Google Sign-In.
    Verifies Google ID Token, finds/creates user, returns application JWT.
    """
    try:
        db = get_firestore_client()
        app_jwt, internal_user_id = await process_google_signin(
            db, request_data.id_token
        )
        return TokenResponse(access_token=app_jwt, user_id=internal_user_id)
    except GoogleSignInError as e:
        logger.error(f"Google Sign-In failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during Google Sign-In: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during sign-in.",
        )


# --- User Signup Endpoint (Potentially Deprecated or Modified if Google Sign-In is primary) ---
# For now, let's keep it but note that Google Sign-In will also create users.
# This endpoint might be used for other signup methods in the future or admin creation.
@app.post(
    "/signup",
    response_model=UserResponse,
    status_code=201,
    deprecated=True,
    summary="Legacy signup, prefer Google Sign-In",
)
async def api_signup_user(user_data: UserSignupRequest = Body(...)):
    # ... (existing signup logic, but consider how it interacts with Google Sign-In users) ...
    # If you want to prevent duplicate emails across signup methods, add checks.
    try:
        db = get_firestore_client()
        created_user = await create_user(
            db, user_data
        )  # This function needs to ensure it also stores user_id
        return created_user
    except UserServiceError as e:
        logger.warning(f"Signup failed: {e}")
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during signup: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during signup.",
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
            db, current_user.user_id, preference_data  # type: ignore
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
        preferences = await get_user_preferences_from_db(db, current_user.user_id)  # type: ignore
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
        reminders_list: List[UserReminderItem] = await get_user_future_reminders(
            db, current_user.user_id  # type: ignore
        )
        return UserRemindersListResponse(
            user_id=current_user.user_id,  # Use user_id from token # type: ignore
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
            db, current_user.user_id, reminder_id, feedback_payload  # type: ignore
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
