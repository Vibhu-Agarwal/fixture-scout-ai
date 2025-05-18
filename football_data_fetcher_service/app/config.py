# football_data_fetcher_service/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    FIRESTORE_DATABASE_NAME: str | None = os.getenv("FIRESTORE_DATABASE_NAME")
    GCP_PROJECT_ID: str | None = os.getenv("GCP_PROJECT_ID")

    # Firestore Collection Name
    FIXTURES_COLLECTION: str = "fixtures"

    # Data Fetcher Specific
    DEFAULT_LOOKOUT_WINDOW_DAYS: int = int(
        os.getenv("DEFAULT_LOOKOUT_WINDOW_DAYS", "9")
    )  # Default to 9 as requested

    # Data Source Configuration
    # Options: "MOCK", "FOOTBALL_DATA_ORG"
    DATA_SOURCE_TYPE: str = os.getenv("DATA_SOURCE_TYPE", "MOCK").upper()

    # football-data.org specific settings
    FOOTBALL_DATA_API_KEY: str | None = os.getenv("FOOTBALL_DATA_API_KEY")
    FOOTBALL_DATA_API_BASE_URL: str = os.getenv(
        "FOOTBALL_DATA_API_BASE_URL", "http://api.football-data.org/v4"
    )

    # Competitions to fetch for football-data.org
    # CL,PL,BL1,FL1,SA,PD,WC,EC (Champions League, Premier League, Bundesliga, Ligue 1, Serie A, La Liga, World Cup, Euros)
    COMPETITIONS_TO_FETCH: str = os.getenv(
        "COMPETITIONS_TO_FETCH", "CL,PL,BL1,FL1,SA,PD,WC,EC"
    )  # Default to major leagues


settings = Settings()

# Friendly names for competitions (can be expanded)
COMPETITION_FRIENDLY_NAMES = {
    "CL": "UEFA Champions League",
    "PL": "Premier League",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "SA": "Serie A",
    "PD": "La Liga",
    "WC": "FIFA World Cup",
    "EC": "UEFA European Championship",
}
