# football_data_fetcher_service/app/data_sources/football_data_org_source.py
import logging
import datetime
from typing import List, Dict, Any, Optional

import httpx
from pydantic import ValidationError

from ..models import FixtureData, Team
from .interface import IFootballDataSource
from ..config import (
    COMPETITION_FRIENDLY_NAMES,
)

logger = logging.getLogger(__name__)


class FootballDataOrgSourceError(Exception):
    pass


class FootballDataOrgSource(IFootballDataSource):
    def __init__(self, api_key: str | None, base_url: str, competitions: str):
        if not api_key:
            raise FootballDataOrgSourceError(
                "API key for football-data.org is required."
            )
        self.base_url = base_url
        self.competitions_filter = competitions
        headers = {"X-Auth-Token": api_key}
        # A single client for the lifetime of this instance is good practice
        self.http_client = httpx.AsyncClient(headers=headers, timeout=30.0)

    async def _fetch_data_from_api(
        self, date_from: str, date_to: str
    ) -> Dict[str, Any]:
        """Fetches raw match data from the football-data.org API."""
        params = {
            "competitions": self.competitions_filter,
            "dateFrom": date_from,
            "dateTo": date_to,
        }
        url = f"{self.base_url}/matches"
        logger.info(
            f"Fetching data from football-data.org: {url} with params: {params}"
        )
        try:
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx responses
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error fetching data from {e.request.url}: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            raise FootballDataOrgSourceError(
                f"API request failed: {e.response.status_code} - {e.response.text}"
            )
        except httpx.RequestError as e:
            logger.error(
                f"Request error fetching data from {e.request.url}: {e}", exc_info=True
            )
            raise FootballDataOrgSourceError(f"API request failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during API fetch: {e}", exc_info=True)
            raise FootballDataOrgSourceError(f"Unexpected error: {str(e)}")

    def _transform_match_data(self, api_match: Dict[str, Any]) -> Optional[FixtureData]:
        """Transforms a single match item from the API response into our FixtureData model."""
        try:
            # Ensure essential fields are present
            if not all(
                k in api_match
                for k in [
                    "id",
                    "utcDate",
                    "competition",
                    "homeTeam",
                    "awayTeam",
                    "status",
                ]
            ):
                logger.warning(
                    f"Skipping match due to missing essential fields: {api_match.get('id', 'Unknown ID')}"
                )
                return None

            # Convert IDs to string for our Pydantic model
            fixture_id_str = str(api_match["id"])
            home_team_id_str = str(api_match["homeTeam"]["id"])
            away_team_id_str = str(api_match["awayTeam"]["id"])

            # Get friendly competition name, fallback to API name or code
            competition_code = api_match["competition"].get("code")
            api_competition_name = api_match["competition"].get("name")
            league_name = COMPETITION_FRIENDLY_NAMES.get(
                competition_code,
                COMPETITION_FRIENDLY_NAMES.get(
                    api_competition_name,
                    api_competition_name or competition_code or "Unknown League",
                ),
            )
            league_id = competition_code or str(api_match["competition"]["id"])

            # Parse UTC date string to datetime object
            try:
                match_datetime_utc = datetime.datetime.fromisoformat(
                    api_match["utcDate"].replace("Z", "+00:00")
                )
            except ValueError:
                logger.warning(
                    f"Could not parse utcDate '{api_match['utcDate']}' for match {fixture_id_str}. Skipping."
                )
                return None

            home_team_data = api_match["homeTeam"]
            away_team_data = api_match["awayTeam"]

            fixture = FixtureData(
                fixture_id=fixture_id_str,
                home_team=Team(
                    id=home_team_id_str,
                    name=home_team_data.get("name", "Unknown Home Team"),
                    short_name=home_team_data.get("shortName"),
                    tla=home_team_data.get("tla"),
                    crest_url=home_team_data.get("crest"),
                ),
                away_team=Team(
                    id=away_team_id_str,
                    name=away_team_data.get("name", "Unknown Away Team"),
                    short_name=away_team_data.get("shortName"),
                    tla=away_team_data.get("tla"),
                    crest_url=away_team_data.get("crest"),
                ),
                league_name=league_name,
                league_id=league_id,
                match_datetime_utc=match_datetime_utc,
                stage=api_match.get("stage"),
                raw_metadata_blob={
                    "api_competition_name": api_competition_name,
                    "api_competition_id": api_match["competition"]["id"],
                    "api_competition_type": api_match["competition"].get("type"),
                    "api_match_status": api_match["status"],
                    "api_matchday": api_match.get("matchday"),
                    "api_group": api_match.get("group"),  # e.g. "GROUP_A"
                    # Add any other potentially useful fields from API response
                    "last_updated_api": api_match.get("lastUpdated"),
                },
                # source_url can be omitted or constructed if a pattern exists
            )
            return fixture
        except ValidationError as e:
            logger.error(
                f"Pydantic validation error transforming API match data for ID {api_match.get('id')}: {e}",
                exc_info=True,
            )
            return None
        except KeyError as e:
            logger.error(
                f"Missing key transforming API match data for ID {api_match.get('id')}: {e}",
                exc_info=True,
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error transforming API match ID {api_match.get('id')}: {e}",
                exc_info=True,
            )
            return None

    async def get_upcoming_matches(self, days_ahead: int = 9) -> List[FixtureData]:
        """Fetches matches for the next 'days_ahead' days."""
        today = datetime.date.today()
        date_from_str = today.isoformat()
        date_to_obj = today + datetime.timedelta(
            days=days_ahead - 1
        )  # API is inclusive, so if days_ahead=1, date_to = today
        date_to_str = date_to_obj.isoformat()

        logger.info(
            f"football-data.org: Requesting matches from {date_from_str} to {date_to_str}."
        )

        try:
            api_response_data = await self._fetch_data_from_api(
                date_from_str, date_to_str
            )
        except FootballDataOrgSourceError:
            return []  # Return empty list on API error to prevent breaking the flow

        transformed_fixtures: List[FixtureData] = []
        if "matches" in api_response_data and isinstance(
            api_response_data["matches"], list
        ):
            for api_match in api_response_data["matches"]:
                # We are interested in SCHEDULED or TIMED matches primarily
                if api_match.get("status") in ["SCHEDULED", "TIMED"]:
                    fixture_obj = self._transform_match_data(api_match)
                    if fixture_obj:
                        transformed_fixtures.append(fixture_obj)
                else:
                    logger.debug(
                        f"Skipping match {api_match.get('id')} with status: {api_match.get('status')}"
                    )
        else:
            logger.warning(
                "No 'matches' array found in API response or it's not a list."
            )
            logger.debug(f"API Response dump: {api_response_data}")

        logger.info(
            f"football-data.org: Fetched and transformed {len(transformed_fixtures)} upcoming matches."
        )
        return transformed_fixtures

    async def close(self):  # Good practice to allow closing the client
        if self.http_client:
            await self.http_client.aclose()
            logger.info("FootballDataOrgSource HTTP client closed.")
