# scout_service/app/firestore_client.py
import logging
from google.cloud import firestore
from .config import settings

logger = logging.getLogger(__name__)

db_client = None


def get_firestore_client():
    global db_client
    if db_client is None:
        try:
            if settings.FIRESTORE_DATABASE_NAME:
                db_client = firestore.Client(database=settings.FIRESTORE_DATABASE_NAME)
                logger.info(
                    f"Firestore client initialized for database: {settings.FIRESTORE_DATABASE_NAME}"
                )
            else:
                db_client = firestore.Client()
                logger.info("Firestore client initialized for default database.")
        except Exception as e:
            logger.error(
                f"Could not initialize Firestore client. Error: {e}", exc_info=True
            )
            raise  # Re-raise the exception to halt app startup if DB is critical
    return db_client


# You can add more Firestore interaction helper functions here if they become complex
# For example, batch write helpers, generic fetch functions, etc.
