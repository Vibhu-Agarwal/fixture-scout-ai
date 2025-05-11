import os
import sys
import uuid
import logging

from flask import Flask, request, jsonify
from google.cloud import firestore

from common import firestore_schema


# --- Logging Setup ---
# Get the function name from the environment variable (K_SERVICE is set by Cloud Functions)
function_name = os.environ.get("K_SERVICE", "register_user_api_local")
logger = logging.getLogger(function_name)
logger.setLevel(logging.INFO)
# Configure logging to output to standard output (picked up by Cloud Logging)
if not logger.handlers:  # Avoid adding multiple handlers during function re-invocations
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        f"%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# --- Flask App Initialization ---
app = Flask(__name__)

# --- Firestore Client Initialization ---
# Initialize outside of request handling for better performance (reuses client across invocations)
try:
    db = firestore.Client(database=firestore_schema.DATABASE_ID)
    logger.info("Firestore client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Firestore client: {e}", exc_info=True)
    db = None  # Ensure db is None if initialization fails


# --- API Endpoint ---
@app.route("/users/register", methods=["POST"])
def register_user():
    """
    Registers a new user.
    Expects JSON payload with 'name' and 'email'. 'phone_number' is optional.
    """
    if not db:
        logger.error("Firestore client is not available.")
        return (
            jsonify(
                {"error": "Internal server error: Firestore client not initialized"}
            ),
            500,
        )

    try:
        logger.info(
            f"Received request to /users/register. Request ID: {request.headers.get('Function-Execution-Id')}"
        )
        data = request.get_json()

        if not data:
            logger.warning("Request body is empty or not JSON.")
            return (
                jsonify({"error": "Invalid request: No data provided or not JSON"}),
                400,
            )

        name = data.get(firestore_schema.USER_NAME_FIELD)
        email = data.get(firestore_schema.USER_EMAIL_FIELD)
        phone_number = data.get(firestore_schema.USER_PHONE_NUMBER_FIELD)  # Optional

        if not name or not email:
            logger.warning(f"Missing required fields. Name: {name}, Email: {email}")
            return (
                jsonify(
                    {
                        "error": "Missing required fields: 'name' and 'email' are required"
                    }
                ),
                400,
            )

        # Validate email format (basic validation)
        if "@" not in email or "." not in email.split("@")[-1]:
            logger.warning(f"Invalid email format: {email}")
            return jsonify({"error": "Invalid email format"}), 400

        user_id = str(uuid.uuid4())
        logger.info(f"Generated new user ID: {user_id} for email: {email}")

        user_doc_ref = db.collection(firestore_schema.USERS_COLLECTION).document(
            user_id
        )

        # Prepare user data, using Firestore server timestamp for creation/update times
        current_time = firestore.SERVER_TIMESTAMP  # Use server timestamp

        user_data = {
            firestore_schema.USER_NAME_FIELD: name,
            firestore_schema.USER_EMAIL_FIELD: email,
            firestore_schema.USER_PREFERENCES_RAW_FIELD: {  # Initialize with empty preferences
                firestore_schema.USER_PREF_FAV_TEAMS: [],
                firestore_schema.USER_PREF_OTHER_TEAMS: [],
                firestore_schema.USER_PREF_LIKED_EXAMPLES: [],
                firestore_schema.USER_PREF_CUSTOM_SNIPPET: "",
            },
            firestore_schema.USER_ACTIVE_GEMINI_PROMPT_FIELD: "",  # Initialize empty
            firestore_schema.USER_FCM_TOKENS_FIELD: [],  # Initialize empty
            firestore_schema.USER_CREATED_AT_FIELD: current_time,
            firestore_schema.USER_UPDATED_AT_FIELD: current_time,
        }
        if phone_number:  # Add phone number only if provided
            user_data[firestore_schema.USER_PHONE_NUMBER_FIELD] = phone_number

        user_doc_ref.set(user_data)
        logger.info(f"User document created successfully for user ID: {user_id}")

        return (
            jsonify(
                {
                    "message": "User registered successfully",
                    "id": user_id,
                }
            ),
            201,
        )

    except Exception as e:
        logger.error(f"An error occurred during user registration: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500


# --- Entry point for Google Cloud Functions ---
# This 'main_app' will be specified as the entry point in gcloud deploy command
main_app = app

if __name__ == "__main__":
    # This is for local development/testing only
    # When deployed to Cloud Functions, a Gunicorn server (or similar) will run the app.
    logger.info("Running Flask app locally for development.")
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
