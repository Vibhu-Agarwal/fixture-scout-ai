# fixture-scout-ai/common/firestore_schema.py

import logging

# Basic logger setup for this module if needed, though typically functions will have their own
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Project Name (can be used in logging, etc.) ---
PROJECT_NAME = "FixtureScoutAI"

# --- Collection Names ---
USERS_COLLECTION = "users"
GLOBAL_UPCOMING_MATCHES_COLLECTION = "global_upcoming_matches"
USER_SCHEDULED_REMINDERS_COLLECTION = (
    "user_scheduled_reminders"  # Storing one reminder task per document
)

# --- User Document Fields (in USERS_COLLECTION) ---
# Document ID for this collection will be the generated UUID (userId)
# No separate USER_ID_FIELD needed if doc ID is the userId.
USER_NAME_FIELD = "name"
USER_EMAIL_FIELD = "email"
USER_PHONE_NUMBER_FIELD = "phone_number"  # Optional
USER_FCM_TOKENS_FIELD = (
    "fcm_tokens"  # Array of strings, for push notifications (future)
)
USER_PREFERENCES_RAW_FIELD = "preferences_raw"  # Object
# Sub-fields for USER_PREFERENCES_RAW_FIELD:
USER_PREF_FAV_TEAMS = "favorite_teams"  # Array of strings
USER_PREF_OTHER_TEAMS = "other_followed_teams"  # Array of strings
USER_PREF_LIKED_EXAMPLES = "liked_match_examples"  # Array of strings
USER_PREF_CUSTOM_SNIPPET = "custom_prompt_snippet"  # String
USER_ACTIVE_GEMINI_PROMPT_FIELD = "active_gemini_prompt"  # String
USER_CREATED_AT_FIELD = "created_at"  # Firestore Server Timestamp
USER_UPDATED_AT_FIELD = "updated_at"  # Firestore Server Timestamp

# --- Global Upcoming Match Document Fields (in GLOBAL_UPCOMING_MATCHES_COLLECTION) ---
# Document ID for this collection will be match_api_id from the sports API
GMATCH_HOME_TEAM_FIELD = "homeTeam"
GMATCH_AWAY_TEAM_FIELD = "awayTeam"
GMATCH_KICKOFF_UTC_FIELD = "kickoffTimeUTC"  # Firestore Timestamp
GMATCH_LEAGUE_NAME_FIELD = "leagueName"
GMATCH_STATUS_FIELD = "status"  # String: e.g., "NEW_GLOBAL", "PROCESSING_USERS_STARTED"
GMATCH_FETCHED_AT_FIELD = "fetched_at"  # Firestore Server Timestamp

# --- User Scheduled Reminder Document Fields (in USER_SCHEDULED_REMINDERS_COLLECTION) ---
# Document ID for this collection will be an auto-generated unique ID by Firestore
REMINDER_USER_ID_FIELD = "userId"  # String (references doc ID in USERS_COLLECTION)
REMINDER_MATCH_API_ID_FIELD = (
    "match_api_id"  # String (references doc ID in GLOBAL_UPCOMING_MATCHES_COLLECTION)
)
REMINDER_KICKOFF_UTC_FIELD = "kickoffTimeUTC"  # Firestore Timestamp (denormalized)
REMINDER_HOME_TEAM_FIELD = "homeTeam"  # String (denormalized)
REMINDER_AWAY_TEAM_FIELD = "awayTeam"  # String (denormalized)
REMINDER_LEAGUE_NAME_FIELD = "leagueName"  # String (denormalized)
REMINDER_GEMINI_IMPORTANCE_FIELD = "gemini_importance_score"  # Number
REMINDER_GEMINI_REASONING_FIELD = "gemini_reasoning"  # String
REMINDER_REMIND_AT_UTC_FIELD = "remind_at_utc"  # Firestore Timestamp
REMINDER_MODE_FIELD = "mode"  # String: e.g., "email" (initially)
REMINDER_MESSAGE_SUBJECT_FIELD = "message_subject"  # String
REMINDER_MESSAGE_BODY_FIELD = "message_body"  # String
REMINDER_SENT_STATUS_FIELD = "sent_status"  # Boolean
REMINDER_CREATED_AT_FIELD = "created_at"  # Firestore Server Timestamp

logger.info(f"{PROJECT_NAME}: Firestore schema constants defined.")
