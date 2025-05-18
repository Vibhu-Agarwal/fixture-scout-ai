# football_data_fetcher_service/app/services/fixture_processing_service.py
import logging
import datetime
from typing import List, Dict, Any

from google.cloud import firestore
from pydantic import BaseModel # For type hinting if fixture_data.home_team is a BaseModel, though model_dump should handle it.

from ..config import settings
from ..models import FixtureData # Ensure this is the Pydantic model
from ..data_sources.interface import IFootballDataSource

logger = logging.getLogger(__name__)

class FixtureStorageError(Exception):
    """Custom exception for errors during fixture storage."""
    pass

async def fetch_and_store_fixtures(
    db: firestore.Client,
    data_source: IFootballDataSource,
    days_ahead: int
) -> Dict[str, Any]:
    """
    Fetches upcoming fixtures from the data_source and stores them in Firestore.
    Returns a summary of the operation.
    """
    logger.info(f"FixtureProcessing: Fetching fixtures for {days_ahead} days ahead.")
    try:
        upcoming_fixtures = await data_source.get_upcoming_matches(days_ahead=days_ahead)
    except Exception as e:
        logger.error(f"FixtureProcessing: Error fetching data from source: {e}", exc_info=True)
        raise FixtureStorageError(f"Error fetching data from source: {str(e)}")

    if not upcoming_fixtures:
        logger.info("FixtureProcessing: No new fixtures fetched or data source returned empty.")
        return {
            "message": "No new fixtures fetched or data source returned empty.",
            "newly_stored": 0,
            "updated": 0,
            "total_from_source": 0
        }

    stored_count = 0
    updated_count = 0
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # We'll process in batches to be efficient with Firestore writes
    # For Firestore, a batch can contain up to 500 operations.
    # Each set() is one operation.
    batch = db.batch()
    operations_in_current_batch = 0
    MAX_OPERATIONS_PER_BATCH = 490 # Keep a small margin

    for fixture_data_item in upcoming_fixtures:
        try:
            # Ensure fixture_data_item is an instance of our Pydantic model for consistency
            # This provides validation if the data source returns raw dicts
            if not isinstance(fixture_data_item, FixtureData):
                logger.warning(f"FixtureProcessing: Received non-FixtureData object from source: {type(fixture_data_item)}. Attempting to parse.")
                current_fixture_pydantic = FixtureData(**fixture_data_item)
            else:
                current_fixture_pydantic = fixture_data_item

            fixture_dict_to_store = current_fixture_pydantic.model_dump(exclude_none=True)
            
            # Ensure `last_fetched_at` is always updated to the current time
            fixture_dict_to_store["last_fetched_at"] = now_utc

            doc_ref = db.collection(settings.FIXTURES_COLLECTION).document(current_fixture_pydantic.fixture_id)
            
            # To accurately count new vs. updated, we need to check existence first.
            # This adds one read operation per fixture.
            # For very high volume, you might optimize this, but for clarity and accuracy, it's good.
            existing_doc_snap = doc_ref.get() # Blocking call

            if existing_doc_snap.exists:
                updated_count += 1
                logger.debug(f"FixtureProcessing: Preparing to update fixture_id {current_fixture_pydantic.fixture_id}")
            else:
                stored_count += 1
                logger.debug(f"FixtureProcessing: Preparing to store new fixture_id {current_fixture_pydantic.fixture_id}")
            
            # Add the set operation to the batch.
            # `merge=True` is not strictly necessary here if we are setting the whole document,
            # but it doesn't hurt and is good practice if you ever send partial updates.
            # If not using merge=True, ensure fixture_dict_to_store contains ALL fields.
            batch.set(doc_ref, fixture_dict_to_store, merge=True)
            operations_in_current_batch += 1

            # Commit batch if it's full
            if operations_in_current_batch >= MAX_OPERATIONS_PER_BATCH:
                batch.commit() # Blocking call
                logger.info(f"FixtureProcessing: Committed a batch of {operations_in_current_batch} fixture operations.")
                batch = db.batch() # Start a new batch
                operations_in_current_batch = 0

        except ValidationError as ve:
            logger.error(f"FixtureProcessing: Pydantic validation error for a fixture: {ve}. Skipping this item.", exc_info=True)
            # Decide if to log the problematic data item (carefully, if it contains PII)
            # logger.debug(f"Problematic fixture data: {fixture_data_item}")
            continue # Skip this fixture
        except Exception as e:
            fixture_id_log = current_fixture_pydantic.fixture_id if 'current_fixture_pydantic' in locals() and hasattr(current_fixture_pydantic, 'fixture_id') else 'UNKNOWN_ID'
            logger.error(f"FixtureProcessing: Error processing fixture_id {fixture_id_log}: {e}", exc_info=True)
            # Decide if one bad fixture should stop the whole batch. For now, continue.
            continue

    # Commit any remaining operations in the last batch
    if operations_in_current_batch > 0:
        batch.commit() # Blocking call
        logger.info(f"FixtureProcessing: Committed final batch of {operations_in_current_batch} fixture operations.")

    summary_message = (
        f"FixtureProcessing: Fixtures processed. "
        f"Newly Stored: {stored_count}, Updated: {updated_count}, "
        f"Total from Source: {len(upcoming_fixtures)}"
    )
    logger.info(summary_message)
    return {
        "message": summary_message,
        "newly_stored": stored_count,
        "updated": updated_count,
        "total_from_source": len(upcoming_fixtures)
    }