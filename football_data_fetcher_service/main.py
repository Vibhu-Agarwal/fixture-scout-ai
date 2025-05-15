# football_data_fetcher_service/main.py

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Protocol
import datetime
import hashlib  # For generating fixture_id from mock data
import os

from google.cloud import firestore

from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# --- Configuration ---
# Initialize Firestore client (handle potential custom database name)
DATABASE_NAME = os.getenv("FIRESTORE_DATABASE_NAME")  # Will be None if not set
if DATABASE_NAME:
    db = firestore.Client(database=DATABASE_NAME)
else:
    db = firestore.Client()  # Tries to use (default)

app = FastAPI(
    title="Football Data Fetcher Service",
    description="Fetches football match data and stores it.",
    version="0.1.0",
)


# --- Pydantic Models for Fixture Data ---
class Team(BaseModel):
    id: str
    name: str


class FixtureData(BaseModel):
    fixture_id: str = Field(description="Unique identifier for the fixture")
    home_team: Team
    away_team: Team
    league_name: str
    league_id: str
    match_datetime_utc: datetime.datetime
    stage: str | None = None
    source_url: str | None = None
    raw_metadata_blob: Dict[str, Any] | None = (
        None  # Store as dict, Firestore handles map
    )
    last_fetched_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


# --- Firestore Collection Name ---
FIXTURES_COLLECTION = "fixtures"


# --- Data Source Interface (Protocol) ---
class IFootballDataSource(Protocol):
    async def get_upcoming_matches(self, days_ahead: int = 7) -> List[FixtureData]: ...


# --- Mock Data Source Implementation ---
class ConstantFootballDataSource:
    async def get_upcoming_matches(self, days_ahead: int = 7) -> List[FixtureData]:
        """
        Returns a list of hardcoded future matches.
        Generates a deterministic fixture_id based on team names and date.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        fixtures = []

        # Helper to create fixture_id
        def create_fixture_id(home_name, away_name, match_date_str):
            # Simple hash for mock data; real APIs provide IDs
            s = f"{home_name}-{away_name}-{match_date_str}"
            return hashlib.md5(s.encode("utf-8")).hexdigest()[:12]

        # Match 1: Real Madrid vs Barcelona (El Clasico) - Tomorrow
        match_date_1 = now + datetime.timedelta(days=1)
        match_date_1_str = match_date_1.strftime("%Y-%m-%d")
        fixtures.append(
            FixtureData(
                fixture_id=create_fixture_id(
                    "Real Madrid", "Barcelona", match_date_1_str
                ),
                home_team=Team(id="real_madrid_01", name="Real Madrid"),
                away_team=Team(id="barcelona_01", name="Barcelona"),
                league_name="La Liga",
                league_id="LL01",
                match_datetime_utc=match_date_1.replace(
                    hour=19, minute=0, second=0, microsecond=0
                ),
                stage="League",
                raw_metadata_blob={"rivalry": "El Clasico", "notes": "Key title match"},
            )
        )

        # Match 2: Man City vs Liverpool - In 3 days
        match_date_2 = now + datetime.timedelta(days=3)
        match_date_2_str = match_date_2.strftime("%Y-%m-%d")
        fixtures.append(
            FixtureData(
                fixture_id=create_fixture_id(
                    "Manchester City", "Liverpool", match_date_2_str
                ),
                home_team=Team(id="mancity_01", name="Manchester City"),
                away_team=Team(id="liverpool_01", name="Liverpool"),
                league_name="Premier League",
                league_id="PL01",
                match_datetime_utc=match_date_2.replace(
                    hour=15, minute=30, second=0, microsecond=0
                ),
                stage="League",
                raw_metadata_blob={
                    "importance": "High",
                    "form_home": "WWDWW",
                    "form_away": "WWLWD",
                },
            )
        )

        # Match 3: Bayern Munich vs Borussia Dortmund (Der Klassiker) - In 5 days
        match_date_3 = now + datetime.timedelta(days=5)
        match_date_3_str = match_date_3.strftime("%Y-%m-%d")
        fixtures.append(
            FixtureData(
                fixture_id=create_fixture_id(
                    "Bayern Munich", "Borussia Dortmund", match_date_3_str
                ),
                home_team=Team(id="bayern_01", name="Bayern Munich"),
                away_team=Team(id="dortmund_01", name="Borussia Dortmund"),
                league_name="Bundesliga",
                league_id="BL01",
                match_datetime_utc=match_date_3.replace(
                    hour=16, minute=30, second=0, microsecond=0
                ),
                stage="League",
                raw_metadata_blob={"rivalry": "Der Klassiker"},
            )
        )

        # Match 4: PSG vs AC Milan - Champions League - In 2 days
        match_date_4 = now + datetime.timedelta(days=2)
        match_date_4_str = match_date_4.strftime("%Y-%m-%d")
        fixtures.append(
            FixtureData(
                fixture_id=create_fixture_id(
                    "Paris Saint-Germain", "AC Milan", match_date_4_str
                ),
                home_team=Team(id="psg_01", name="Paris Saint-Germain"),
                away_team=Team(id="acmilan_01", name="AC Milan"),
                league_name="Champions League",
                league_id="UCL01",
                match_datetime_utc=match_date_4.replace(
                    hour=20, minute=0, second=0, microsecond=0
                ),
                stage="Group Stage",
            )
        )

        # Match 5: A less "big" match, but for variety - In 4 days
        match_date_5 = now + datetime.timedelta(days=4)
        match_date_5_str = match_date_5.strftime("%Y-%m-%d")
        fixtures.append(
            FixtureData(
                fixture_id=create_fixture_id(
                    "Brighton & Hove Albion", "Fulham", match_date_5_str
                ),
                home_team=Team(id="brighton_01", name="Brighton & Hove Albion"),
                away_team=Team(id="fulham_01", name="Fulham"),
                league_name="Premier League",
                league_id="PL01",
                match_datetime_utc=match_date_5.replace(
                    hour=14, minute=0, second=0, microsecond=0
                ),
                stage="League",
            )
        )

        # Filter for 'days_ahead' - simple example, could be more precise
        return [
            f
            for f in fixtures
            if f.match_datetime_utc <= now + datetime.timedelta(days=days_ahead)
        ]


# --- Dependency Injection for Data Source ---
# For now, we directly instantiate ConstantFootballDataSource.
# Later, this could be made more configurable (e.g., based on env var).
def get_football_data_source() -> IFootballDataSource:
    return ConstantFootballDataSource()


LOOKOUT_WINDOW = 14  # Days ahead to fetch fixtures


# --- API Endpoint ---
@app.post("/fetch-and-store-fixtures", status_code=200)
async def fetch_and_store_fixtures_endpoint(
    data_source: IFootballDataSource = Depends(get_football_data_source),
):
    """
    Fetches upcoming football fixtures from the configured data source
    and stores them in Firestore. Implements idempotency.
    """
    if not db:
        raise HTTPException(status_code=500, detail="Firestore client not initialized.")

    try:
        upcoming_fixtures = await data_source.get_upcoming_matches(
            days_ahead=LOOKOUT_WINDOW
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching data from source: {str(e)}"
        )

    if not upcoming_fixtures:
        return {"message": "No new fixtures fetched or data source returned empty."}

    stored_count = 0
    updated_count = 0
    skipped_count = 0  # For fixtures that are identical and don't need update

    batch = db.batch()
    fixtures_processed_in_batch = 0

    for fixture_data in upcoming_fixtures:
        fixture_dict = fixture_data.model_dump(
            exclude_none=True
        )  # Use model_dump for Pydantic v2

        # Convert Pydantic nested models to dicts if Firestore client needs it
        # (Pydantic v2 model_dump should handle this, but being explicit can help)
        if "home_team" in fixture_dict and isinstance(
            fixture_dict["home_team"], BaseModel
        ):
            fixture_dict["home_team"] = fixture_dict["home_team"].model_dump()
        if "away_team" in fixture_dict and isinstance(
            fixture_dict["away_team"], BaseModel
        ):
            fixture_dict["away_team"] = fixture_dict["away_team"].model_dump()

        fixture_dict["last_fetched_at"] = datetime.datetime.now(
            datetime.timezone.utc
        )  # Always update this

        doc_ref = db.collection(FIXTURES_COLLECTION).document(fixture_data.fixture_id)

        # Idempotency check:
        # For Phase 1 with mock data, we can simply overwrite or check existence.
        # A more robust check would compare existing data with new data.
        existing_doc = doc_ref.get()
        if existing_doc.exists:
            # Simple update: Overwrite.
            # For more sophisticated updates, compare fields before deciding to write.
            # For now, we'll assume our mock data might "change" (e.g. if we edit the source)
            # so we'll update.
            # If you want to avoid writes if data is identical:
            # existing_data = existing_doc.to_dict()
            # if existing_data == fixture_dict (excluding last_fetched_at for comparison):
            #    skipped_count += 1
            #    continue
            batch.set(
                doc_ref, fixture_dict, merge=True
            )  # merge=True is good for updates
            updated_count += 1
        else:
            batch.set(doc_ref, fixture_dict)
            stored_count += 1

        fixtures_processed_in_batch += 1
        if (
            fixtures_processed_in_batch >= 490
        ):  # Firestore batch limit is 500 operations
            batch.commit()
            batch = db.batch()  # Start a new batch
            fixtures_processed_in_batch = 0

    if fixtures_processed_in_batch > 0:  # Commit any remaining operations
        batch.commit()

    return {
        "message": "Fixtures processed.",
        "newly_stored": stored_count,
        "updated": updated_count,
        "skipped_identical": skipped_count,  # Will be 0 with current logic
        "total_from_source": len(upcoming_fixtures),
    }


@app.get("/")
async def read_root():
    return {
        "message": "Welcome to the Fixture Scout AI - Football Data Fetcher Service"
    }
