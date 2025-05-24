# user_management_service/app/firebase_admin_init.py
import firebase_admin
import logging

logger = logging.getLogger(__name__)
_firebase_app_initialized = False


def initialize_firebase_admin():
    global _firebase_app_initialized
    if not _firebase_app_initialized:
        try:
            firebase_admin.initialize_app()  # Simplest form, relies on ADC or GCP environment

            logger.info("Firebase Admin SDK initialized successfully.")
            _firebase_app_initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {e}", exc_info=True)
            # This is a critical failure for auth.
            raise RuntimeError(f"Firebase Admin SDK initialization failed: {e}")
