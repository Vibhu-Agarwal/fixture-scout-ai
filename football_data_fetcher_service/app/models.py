# football_data_fetcher_service/app/models.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import datetime


class Team(BaseModel):
    id: str
    name: str
    # We can add shortName, tla, crest later if needed by the LLM or display
    short_name: Optional[str] = None
    tla: Optional[str] = None
    crest_url: Optional[str] = None


class FixtureData(BaseModel):
    fixture_id: str = Field(description="Unique identifier for the fixture")
    home_team: Team
    away_team: Team
    league_name: str
    league_id: str
    match_datetime_utc: datetime.datetime
    stage: Optional[str] = None
    source_url: Optional[str] = None
    raw_metadata_blob: Optional[Dict[str, Any]] = None
    last_fetched_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
