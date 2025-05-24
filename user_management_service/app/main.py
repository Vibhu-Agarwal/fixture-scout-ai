# user_management_service/app/main.py
import logging
import os
from fastapi import FastAPI, HTTPException, Body, Path
from contextlib import asynccontextmanager
from typing import List  # For response model typing

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
    UserFeedbackCreateRequest,
    UserFeedbackDoc,
)
from .services.user_service import (  # New imports
    store_user_feedback,
    create_user,
    set_user_preferences,
    get_user_preferences_from_db,
    UserServiceError,
    UserNotFoundError,
    PreferenceNotFoundError,
    FeedbackSubmissionError,
)
from .services.reminder_query_service import (  # New imports
    get_user_future_reminders,
    ReminderQueryError,
)

logger = logging.getLogger(__name__)


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
    description="Manages user signups, preferences, and lists their reminders.",
    version="0.2.0",  # Incremented version
    lifespan=lifespan,
)


# --- User Signup and Preference Endpoints ---
@app.post("/signup", response_model=UserResponse, status_code=201)
async def api_signup_user(user_data: UserSignupRequest = Body(...)):
    try:
        db = get_firestore_client()
        created_user = await create_user(db, user_data)
        return created_user
    except UserServiceError as e:
        logger.warning(f"Signup failed: {e}")
        raise HTTPException(status_code=409, detail=str(e))  # Conflict if user exists
    except Exception as e:
        logger.error(f"Unexpected error during signup: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An internal error occurred during signup."
        )


@app.put("/users/{user_id}/preferences", response_model=UserPreferenceResponse)
async def api_submit_user_preferences(
    user_id: str = Path(..., description="The unique ID of the user"),
    preference_data: UserPreferenceSubmitRequest = Body(...),
):
    try:
        db = get_firestore_client()
        updated_preference = await set_user_preferences(db, user_id, preference_data)
        return updated_preference
    except UserNotFoundError as e:
        logger.warning(f"Set preferences failed, user not found: {user_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error setting preferences for user {user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while setting preferences.",
        )


@app.get("/users/{user_id}/preferences", response_model=UserPreferenceResponse)
async def api_get_user_preferences(
    user_id: str = Path(..., description="The unique ID of the user")
):
    try:
        db = get_firestore_client()
        preferences = await get_user_preferences_from_db(db, user_id)
        return preferences
    except PreferenceNotFoundError as e:
        logger.warning(f"Get preferences failed, not found for user: {user_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error getting preferences for user {user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while getting preferences.",
        )


# --- New Endpoint for Listing User Reminders ---
@app.get("/users/{user_id}/reminders", response_model=UserRemindersListResponse)
async def api_get_user_reminders(
    user_id: str = Path(..., description="The unique ID of the user")
):
    """
    Retrieves a list of all upcoming reminders for the specified user,
    enriched with basic fixture details.
    """
    try:
        db = get_firestore_client()
        # First, check if user exists.
        user_doc_ref = db.collection(settings.USERS_COLLECTION).document(user_id)
        if not user_doc_ref.get().exists:
            logger.warning(f"Attempt to get reminders for non-existent user: {user_id}")
            raise HTTPException(
                status_code=404, detail=f"User with ID {user_id} not found."
            )

        reminders_list: List[UserReminderItem] = await get_user_future_reminders(
            db, user_id
        )
        return UserRemindersListResponse(
            user_id=user_id, reminders=reminders_list, count=len(reminders_list)
        )
    except ReminderQueryError as e:  # Custom error from the service if needed
        logger.error(f"Error querying reminders for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Could not retrieve reminders: {str(e)}"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error fetching reminders for user {user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred while fetching reminders.",
        )


@app.post(
    "/users/{user_id}/reminders/{reminder_id}/feedback",
    response_model=UserFeedbackDoc,
    status_code=201,
)
async def api_submit_reminder_feedback(
    user_id: str = Path(..., description="The ID of the user submitting feedback"),
    reminder_id: str = Path(
        ..., description="The ID of the reminder this feedback is for"
    ),
    feedback_payload: UserFeedbackCreateRequest = Body(...),
):
    """
    Allows a user to submit feedback (e.g., "not interested") for a specific reminder.
    """
    # In a real system with JWT auth, user_id would come from token and be compared to path user_id
    # For now, we assume path user_id is authoritative for this endpoint.
    try:
        db = get_firestore_client()
        # Here, you'd also check if the authenticated user matches user_id from path
        # For now, we proceed.

        feedback_doc = await store_user_feedback(
            db, user_id, reminder_id, feedback_payload
        )
        return feedback_doc
    except FeedbackSubmissionError as e:
        logger.warning(
            f"Feedback submission failed for user {user_id}, reminder {reminder_id}: {e}"
        )
        # Determine appropriate HTTP status code based on error type
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        elif "forbidden" in str(e).lower():
            raise HTTPException(status_code=403, detail=str(e))
        else:
            raise HTTPException(
                status_code=400, detail=str(e)
            )  # Bad Request for other submission errors
    except Exception as e:
        logger.error(
            f"Unexpected error submitting feedback for user {user_id}, reminder {reminder_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while submitting feedback.",
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
