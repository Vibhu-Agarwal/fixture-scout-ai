# football_data_fetcher_service/app/main.py
import logging
import os
from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager

from .utils.logging_config import setup_logging
setup_logging()

from .config import settings
from .firestore_client import get_firestore_client
from .data_sources.interface import IFootballDataSource
from .data_sources.mock_data_source import ConstantFootballDataSource # For default P1 source
from .services.fixture_processing_service import fetch_and_store_fixtures, FixtureStorageError

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Football Data Fetcher Service starting up...")
    try:
        get_firestore_client() # Initialize Firestore client
        logger.info("DataFetcher Firestore client initialized successfully on startup.")
    except Exception as e:
        logger.critical(f"DataFetcher: Failed to initialize Firestore client on startup: {e}", exc_info=True)
    yield
    logger.info("Football Data Fetcher Service shutting down...")

app = FastAPI(
    title="Football Data Fetcher Service",
    description="Fetches football match data from a configured source and stores it.",
    version="0.1.1",
    lifespan=lifespan
)

# --- Dependency Injection for Data Source ---
# This allows easy swapping of data sources in the future.
def get_football_data_source_dependency() -> IFootballDataSource:
    # In the future, this could read settings.DATA_SOURCE_TYPE
    # and instantiate the appropriate class.
    # For Phase 1, we hardcode the mock source.
    return ConstantFootballDataSource()

# --- API Endpoint ---
@app.post("/data-fetcher/fetch-and-store-all-fixtures", status_code=200) # Renamed for clarity
async def api_fetch_and_store_fixtures(
    data_source: IFootballDataSource = Depends(get_football_data_source_dependency),
):
    """
    API endpoint to trigger fetching and storing of football fixtures.
    Intended to be called by Cloud Scheduler.
    """
    try:
        db = get_firestore_client()
        summary = await fetch_and_store_fixtures(
            db,
            data_source,
            days_ahead=settings.DEFAULT_LOOKOUT_WINDOW_DAYS
        )
        return summary
    except FixtureStorageError as e: # Custom error from service layer
        logger.error(f"API: Error during fixture fetching/storage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e: # e.g. if clients not initialized
        logger.critical(f"API: Service runtime error: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")
    except Exception as e:
        logger.error(f"API: Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected internal error occurred: {str(e)}")


@app.get("/")
async def read_root():
    return {"message": "Welcome to the Fixture Scout AI - Football Data Fetcher Service"}

@app.get("/health")
async def health_check():
    db_ok = False
    try:
        get_firestore_client()
        db_ok = True
    except Exception:
        logger.warning("Health check: Firestore client not healthy for DataFetcher service.")
    
    if db_ok:
        return {"status": "ok", "firestore_healthy": True}
    else:
        return {"status": "degraded", "firestore_healthy": False, "detail": "Firestore client issue."}