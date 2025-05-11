import os
import sys
import uuid
import logging

from flask import Flask, request, jsonify
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore import Transaction

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


# --- Transactional User Creation Function ---
@firestore.transactional
def create_user_in_transaction(
    transaction: Transaction, user_id, user_data_to_create, email_to_check
):
    """
    Creates a user document within a transaction, ensuring email uniqueness.
    """
    logger.info(
        f"Transaction {transaction.id}: Checking for existing email: {email_to_check}"
    )

    # 1. Check if email already exists
    users_ref = db.collection(firestore_schema.USERS_COLLECTION)
    # Note: Queries inside transactions must read documents before writing them.
    # We are querying for existence.
    query = users_ref.where(
        filter=FieldFilter(firestore_schema.USER_EMAIL_FIELD, "==", email_to_check)
    ).limit(1)
    docs = list(
        query.stream(transaction=transaction)
    )  # Execute query within transaction

    if docs:
        logger.warning(
            f"Transaction {transaction.id}: Email '{email_to_check}' already exists. User ID: {docs[0].id}"
        )
        # By raising an exception, the transaction will automatically roll back.
        # However, we want to return a specific error message, so we'll return a status.
        return False, "Email already registered."

    # 2. If email does not exist, create the new user document
    user_doc_ref = users_ref.document(user_id)
    transaction.set(user_doc_ref, user_data_to_create)
    logger.info(
        f"Transaction {transaction.id}: User document {user_id} set for creation."
    )
    return True, user_id


# --- API Endpoint ---
@app.route("/users/register", methods=["POST"])
def register_user():
    """
    Registers a new user if the email is not already in use.
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
        request_id = request.headers.get(
            "Function-Execution-Id", str(uuid.uuid4())
        )  # Get execution ID or generate one
        logger.info(f"Request ID {request_id}: Received request to /users/register.")
        data = request.get_json()

        if not data:
            logger.warning(
                f"Request ID {request_id}: Request body is empty or not JSON."
            )
            return (
                jsonify({"error": "Invalid request: No data provided or not JSON"}),
                400,
            )

        name = data.get(firestore_schema.USER_NAME_FIELD)
        email = data.get(firestore_schema.USER_EMAIL_FIELD)
        phone_number = data.get(firestore_schema.USER_PHONE_NUMBER_FIELD)

        if not name or not email:
            logger.warning(
                f"Request ID {request_id}: Missing required fields. Name: {name}, Email: {email}"
            )
            return (
                jsonify(
                    {
                        "error": "Missing required fields: 'name' and 'email' are required"
                    }
                ),
                400,
            )

        # Basic email format validation
        if "@" not in email or "." not in email.split("@")[-1]:
            logger.warning(f"Request ID {request_id}: Invalid email format: {email}")
            return jsonify({"error": "Invalid email format"}), 400

        email = (
            email.lower().strip()
        )  # Normalize email: convert to lowercase and strip whitespace

        user_id = str(uuid.uuid4())
        logger.info(
            f"Request ID {request_id}: Attempting registration for email: {email} with potential user ID: {user_id}"
        )

        current_time = firestore.SERVER_TIMESTAMP
        user_data_to_create = {
            firestore_schema.USER_NAME_FIELD: name,
            firestore_schema.USER_EMAIL_FIELD: email,  # Store normalized email
            firestore_schema.USER_PREFERENCES_RAW_FIELD: {
                firestore_schema.USER_PREF_FAV_TEAMS: [],
                firestore_schema.USER_PREF_OTHER_TEAMS: [],
                firestore_schema.USER_PREF_LIKED_EXAMPLES: [],
                firestore_schema.USER_PREF_CUSTOM_SNIPPET: "",
            },
            firestore_schema.USER_ACTIVE_GEMINI_PROMPT_FIELD: "",
            firestore_schema.USER_FCM_TOKENS_FIELD: [],
            firestore_schema.USER_CREATED_AT_FIELD: current_time,
            firestore_schema.USER_UPDATED_AT_FIELD: current_time,
        }
        if phone_number:
            user_data_to_create[firestore_schema.USER_PHONE_NUMBER_FIELD] = (
                phone_number.strip()
            )

        # Run the user creation logic within a transaction
        transaction = db.transaction()
        success, result_message = create_user_in_transaction(
            transaction, user_id, user_data_to_create, email
        )

        if success:
            logger.info(
                f"Request ID {request_id}: User document created successfully for user ID: {result_message} (email: {email})"
            )
            return (
                jsonify(
                    {
                        "message": "User registered successfully",
                        "id": result_message,
                    }
                ),
                201,
            )
        else:
            logger.warning(
                f"Request ID {request_id}: Failed to register user (email: {email}). Reason: {result_message}"
            )
            return (
                jsonify({"error": result_message}),
                409,
            )  # 409 Conflict for existing resource

    except Exception as e:
        request_id = request.headers.get("Function-Execution-Id", "N/A")
        logger.error(
            f"Request ID {request_id}: An error occurred during user registration: {e}",
            exc_info=True,
        )
        return jsonify({"error": "An internal server error occurred"}), 500


# --- Entry point for Google Cloud Functions ---
# This 'main_app' will be specified as the entry point in gcloud deploy command
main_app = app

if __name__ == "__main__":
    # This is for local development/testing only
    # When deployed to Cloud Functions, a Gunicorn server (or similar) will run the app.
    logger.info("Running Flask app locally for development.")
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
