# football_data_fetcher_service/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    FIRESTORE_DATABASE_NAME: str | None = os.getenv("FIRESTORE_DATABASE_NAME")
    GCP_PROJECT_ID: str | None = os.getenv("GCP_PROJECT_ID") # Good to have for client init

    # Firestore Collection Name
    FIXTURES_COLLECTION: str = "fixtures"

    # Data Fetcher Specific
    DEFAULT_LOOKOUT_WINDOW_DAYS: int = int(os.getenv("DEFAULT_LOOKOUT_WINDOW_DAYS", "14"))
    # DATA_SOURCE_TYPE: str = os.getenv("DATA_SOURCE_TYPE", "MOCK") # For future dynamic source selection

settings = Settings()