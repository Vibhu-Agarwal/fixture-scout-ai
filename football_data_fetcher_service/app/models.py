# football_data_fetcher_service/app/models.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional # Added Optional
import datetime

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
    stage: Optional[str] = None # Made Optional consistently
    source_url: Optional[str] = None
    raw_metadata_blob: Optional[Dict[str, Any]] = None
    last_fetched_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )