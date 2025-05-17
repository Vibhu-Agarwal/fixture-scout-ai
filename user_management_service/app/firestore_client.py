# user_management_service/app/firestore_client.py
import logging
import os
from google.cloud import firestore
from .config import settings

logger = logging.getLogger(__name__)
_db_client: firestore.Client | None = None


def get_firestore_client() -> firestore.Client:
    global _db_client
    if _db_client is None:
        try:
            project_id = os.getenv(
                "GCP_PROJECT_ID"
            )  # Firestore client can infer project from ADC
            if settings.FIRESTORE_DATABASE_NAME:
                _db_client = firestore.Client(
                    project=project_id, database=settings.FIRESTORE_DATABASE_NAME
                )
                logger.info(
                    f"UserMgt Firestore client initialized for database: {settings.FIRESTORE_DATABASE_NAME}"
                )
            else:
                _db_client = firestore.Client(project=project_id)
                logger.info(
                    "UserMgt Firestore client initialized for default database."
                )
        except Exception as e:
            logger.error(
                f"UserMgt: Could not initialize Firestore client. Error: {e}",
                exc_info=True,
            )
            raise RuntimeError(f"UserMgt: Failed to initialize Firestore: {e}")
    return _db_client
