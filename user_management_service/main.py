# user_management_service/main.py

from fastapi import FastAPI, HTTPException, Body, Path
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import uuid
from google.cloud import firestore
import datetime
import os


DATABASE_NAME = os.getenv("FIRESTORE_DATABASE_NAME")  # Will be None if not set
if DATABASE_NAME:
    db = firestore.Client(database=DATABASE_NAME)
else:
    db = firestore.Client()  # Tries to use (default)

app = FastAPI(
    title="User Management & Preference Service",
    description="Manages user signups and their LLM prompt preferences.",
    version="0.1.0",
)


# --- Pydantic Models ---


class UserSignupRequest(BaseModel):
    name: str = Field(..., examples=["John Doe"])
    email: EmailStr = Field(..., examples=["john.doe@example.com"])
    phone_number: Optional[str] = Field(None, examples=["+15551234567"])


class UserResponse(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    phone_number: Optional[str]
    created_at: datetime.datetime


class UserPreferenceSubmitRequest(BaseModel):
    # In Phase 1, user directly submits the "optimized" prompt.
    # Later, this might come from the Prompt Optimization Service.
    optimized_llm_prompt: str = Field(
        ...,
        examples=[
            "Remind me of all Real Madrid matches and important Champions League games involving top teams."
        ],
    )


class UserPreferenceResponse(BaseModel):
    user_id: str
    optimized_llm_prompt: str
    updated_at: datetime.datetime


# --- Firestore Collection Names ---
USERS_COLLECTION = "users"
USER_PREFERENCES_COLLECTION = "user_preferences"

# --- API Endpoints ---


@app.post("/signup", response_model=UserResponse, status_code=201)
async def signup_user(user_data: UserSignupRequest = Body(...)):
    """
    Registers a new user and returns their details along with a unique user_id.
    """
    if not db:
        raise HTTPException(status_code=500, detail="Firestore client not initialized.")

    user_id = str(uuid.uuid4())
    created_at = datetime.datetime.now(datetime.timezone.utc)

    user_doc_ref = db.collection(USERS_COLLECTION).document(user_id)

    # Check if user with this email already exists (optional, but good practice)
    # For simplicity in P1, we might skip this unique email check.
    # query = db.collection(USERS_COLLECTION).where("email", "==", user_data.email).limit(1).stream()
    # if any(query):
    #     raise HTTPException(status_code=409, detail=f"User with email {user_data.email} already exists.")

    user_record = {
        "user_id": user_id,  # Storing user_id also in the document body for easier querying if needed
        "name": user_data.name,
        "email": user_data.email,
        "phone_number": user_data.phone_number,
        "created_at": created_at,
    }
    user_doc_ref.set(user_record)

    return UserResponse(**user_record)


@app.put("/users/{user_id}/preferences", response_model=UserPreferenceResponse)
async def submit_user_preferences(
    user_id: str = Path(..., description="The unique ID of the user"),
    preference_data: UserPreferenceSubmitRequest = Body(...),
):
    """
    Allows a user to submit or update their LLM prompt preference.
    In Phase 1, the user directly provides the 'optimized_llm_prompt'.
    """
    if not db:
        raise HTTPException(status_code=500, detail="Firestore client not initialized.")

    user_doc_ref = db.collection(USERS_COLLECTION).document(user_id)
    if not user_doc_ref.get().exists:
        raise HTTPException(
            status_code=404, detail=f"User with ID {user_id} not found."
        )

    preference_doc_ref = db.collection(USER_PREFERENCES_COLLECTION).document(user_id)
    updated_at = datetime.datetime.now(datetime.timezone.utc)

    preference_record = {
        "user_id": user_id,  # Storing user_id also in the document body
        "optimized_llm_prompt": preference_data.optimized_llm_prompt,
        "updated_at": updated_at,
    }
    preference_doc_ref.set(preference_record)  # set() will create or overwrite

    return UserPreferenceResponse(**preference_record)


@app.get("/users/{user_id}/preferences", response_model=UserPreferenceResponse)
async def get_user_preferences(
    user_id: str = Path(..., description="The unique ID of the user")
):
    """
    Retrieves a user's LLM prompt preference.
    """
    if not db:
        raise HTTPException(status_code=500, detail="Firestore client not initialized.")

    preference_doc_ref = db.collection(USER_PREFERENCES_COLLECTION).document(user_id)
    preference_doc = preference_doc_ref.get()

    if not preference_doc.exists:
        raise HTTPException(
            status_code=404,
            detail=f"Preferences for user ID {user_id} not found. Please submit preferences first.",
        )

    return UserPreferenceResponse(**preference_doc.to_dict())


@app.get("/")
async def read_root():
    return {
        "message": "Welcome to the Fixture Scout AI - User Management & Preference Service"
    }
