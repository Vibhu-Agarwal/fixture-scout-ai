# football_data_fetcher_service/app/data_sources/interface.py
from typing import List, Protocol
from ..models import FixtureData # Relative import

class IFootballDataSource(Protocol):
    async def get_upcoming_matches(self, days_ahead: int = 7) -> List[FixtureData]:
        """
        Fetches upcoming football matches.
        """
        ...