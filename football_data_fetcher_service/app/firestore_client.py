# football_data_fetcher_service/app/firestore_client.py
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
            project_id_for_client = settings.GCP_PROJECT_ID # Client can infer from ADC if None
            if settings.FIRESTORE_DATABASE_NAME:
                _db_client = firestore.Client(project=project_id_for_client, database=settings.FIRESTORE_DATABASE_NAME)
                logger.info(f"DataFetcher Firestore client initialized for database: {settings.FIRESTORE_DATABASE_NAME}")
            else:
                _db_client = firestore.Client(project=project_id_for_client)
                logger.info("DataFetcher Firestore client initialized for default database.")
        except Exception as e:
            logger.error(f"DataFetcher: Could not initialize Firestore client. Error: {e}", exc_info=True)
            raise RuntimeError(f"DataFetcher: Failed to initialize Firestore: {e}")
    return _db_client