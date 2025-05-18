# football_data_fetcher_service/app/data_sources/mock_data_source.py
import datetime
import hashlib
from typing import List, Dict, Any # Added Any for raw_metadata_blob consistency
from ..models import FixtureData, Team # Relative import
from .interface import IFootballDataSource # Relative import

class ConstantFootballDataSource(IFootballDataSource): # Implement the interface
    async def get_upcoming_matches(self, days_ahead: int = 7) -> List[FixtureData]:
        """
        Returns a list of hardcoded future matches.
        Generates a deterministic fixture_id based on team names and date.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        fixtures: List[FixtureData] = []

        def create_fixture_id(home_name: str, away_name: str, match_date_str: str) -> str:
            s = f"{home_name}-{away_name}-{match_date_str}"
            return hashlib.md5(s.encode("utf-8")).hexdigest()[:12]

        # Match 1: Real Madrid vs Barcelona (El Clasico)
        match_date_1 = now + datetime.timedelta(days=1)
        match_date_1_str = match_date_1.strftime("%Y-%m-%d")
        fixtures.append(
            FixtureData(
                fixture_id=create_fixture_id("Real Madrid", "Barcelona", match_date_1_str),
                home_team=Team(id="real_madrid_01", name="Real Madrid"),
                away_team=Team(id="barcelona_01", name="Barcelona"),
                league_name="La Liga",
                league_id="LL01",
                match_datetime_utc=match_date_1.replace(hour=19, minute=0, second=0, microsecond=0),
                stage="League",
                raw_metadata_blob={"rivalry": "El Clasico", "notes": "Key title match"},
            )
        )
        # Match 2: Man City vs Liverpool
        match_date_2 = now + datetime.timedelta(days=3)
        match_date_2_str = match_date_2.strftime("%Y-%m-%d")
        fixtures.append(
            FixtureData(
                fixture_id=create_fixture_id("Manchester City", "Liverpool", match_date_2_str),
                home_team=Team(id="mancity_01", name="Manchester City"),
                away_team=Team(id="liverpool_01", name="Liverpool"),
                league_name="Premier League",
                league_id="PL01",
                match_datetime_utc=match_date_2.replace(hour=15, minute=30, second=0, microsecond=0),
                stage="League",
                raw_metadata_blob={"importance": "High", "form_home": "WWDWW", "form_away": "WWLWD"},
            )
        )
        # ... (Add other matches as previously defined) ...
        # Match 3: Bayern Munich vs Borussia Dortmund (Der Klassiker)
        match_date_3 = now + datetime.timedelta(days=5)
        match_date_3_str = match_date_3.strftime("%Y-%m-%d")
        fixtures.append(
            FixtureData(
                fixture_id=create_fixture_id("Bayern Munich", "Borussia Dortmund", match_date_3_str),
                home_team=Team(id="bayern_01", name="Bayern Munich"),
                away_team=Team(id="dortmund_01", name="Borussia Dortmund"),
                league_name="Bundesliga",
                league_id="BL01",
                match_datetime_utc=match_date_3.replace(hour=16, minute=30, second=0, microsecond=0),
                stage="League",
                raw_metadata_blob={"rivalry": "Der Klassiker"},
            )
        )
        # Match 4: PSG vs AC Milan - Champions League
        match_date_4 = now + datetime.timedelta(days=2)
        match_date_4_str = match_date_4.strftime("%Y-%m-%d")
        fixtures.append(
            FixtureData(
                fixture_id=create_fixture_id("Paris Saint-Germain", "AC Milan", match_date_4_str),
                home_team=Team(id="psg_01", name="Paris Saint-Germain"),
                away_team=Team(id="acmilan_01", name="AC Milan"),
                league_name="Champions League",
                league_id="UCL01",
                match_datetime_utc=match_date_4.replace(hour=20, minute=0, second=0, microsecond=0),
                stage="Group Stage",
            )
        )
        # Match 5: Brighton & Hove Albion vs Fulham
        match_date_5 = now + datetime.timedelta(days=4)
        match_date_5_str = match_date_5.strftime("%Y-%m-%d")
        fixtures.append(
            FixtureData(
                fixture_id=create_fixture_id("Brighton & Hove Albion", "Fulham", match_date_5_str),
                home_team=Team(id="brighton_01", name="Brighton & Hove Albion"),
                away_team=Team(id="fulham_01", name="Fulham"),
                league_name="Premier League",
                league_id="PL01",
                match_datetime_utc=match_date_5.replace(hour=14, minute=0, second=0, microsecond=0),
                stage="League",
            )
        )

        return [f for f in fixtures if f.match_datetime_utc <= now + datetime.timedelta(days=days_ahead)]