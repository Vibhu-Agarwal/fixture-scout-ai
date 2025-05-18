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
from .data_sources.mock_data_source import ConstantFootballDataSource
from .data_sources.football_data_org_source import (
    FootballDataOrgSource,
    FootballDataOrgSourceError,
)  # New import
from .services.fixture_processing_service import (
    fetch_and_store_fixtures,
    FixtureStorageError,
)

logger = logging.getLogger(__name__)

# Global instance of the data source, initialized in lifespan
_football_data_source_instance: IFootballDataSource | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _football_data_source_instance
    logger.info("Football Data Fetcher Service starting up...")
    try:
        get_firestore_client()  # Initialize Firestore client
        logger.info("DataFetcher Firestore client initialized successfully on startup.")

        # Initialize the configured data source
        if settings.DATA_SOURCE_TYPE == "FOOTBALL_DATA_ORG":
            if not settings.FOOTBALL_DATA_API_KEY:
                logger.critical(
                    "FOOTBALL_DATA_API_KEY not set but DATA_SOURCE_TYPE is FOOTBALL_DATA_ORG. Service will fail to fetch."
                )
                # This is a critical config error, could raise here to stop startup
                # For now, allow startup but get_football_data_source_dependency will fail.

            _football_data_source_instance = FootballDataOrgSource(
                api_key=settings.FOOTBALL_DATA_API_KEY,
                base_url=settings.FOOTBALL_DATA_API_BASE_URL,
                competitions=settings.COMPETITIONS_TO_FETCH,
            )
            logger.info("Using FootballDataOrgSource.")
        elif settings.DATA_SOURCE_TYPE == "MOCK":
            _football_data_source_instance = ConstantFootballDataSource()
            logger.info("Using ConstantFootballDataSource (Mock).")
        else:
            logger.critical(
                f"Unsupported DATA_SOURCE_TYPE: {settings.DATA_SOURCE_TYPE}. Defaulting to MOCK."
            )
            _football_data_source_instance = ConstantFootballDataSource()

    except Exception as e:
        logger.critical(
            f"DataFetcher: Failed to initialize clients or data source on startup: {e}",
            exc_info=True,
        )

    yield  # Application runs

    # Cleanup: Close the data source if it has a close method (like our httpx client)
    if hasattr(_football_data_source_instance, "close") and callable(
        getattr(_football_data_source_instance, "close")
    ):
        try:
            await _football_data_source_instance.close()  # type: ignore
        except Exception as e:
            logger.error(f"Error closing data source: {e}", exc_info=True)
    logger.info("Football Data Fetcher Service shutting down...")


app = FastAPI(
    title="Football Data Fetcher Service",
    description="Fetches football match data from a configured source and stores it.",
    version="0.1.2",  # Incremented
    lifespan=lifespan,
)


# --- Dependency Injection for Data Source ---
def get_football_data_source_dependency() -> IFootballDataSource:
    if _football_data_source_instance is None:
        # This should not happen if lifespan initializer ran correctly
        logger.error("Football data source accessed before initialization!")
        raise RuntimeError(
            "Football data source not initialized. Check service startup."
        )
    return _football_data_source_instance


# --- API Endpoint (remains largely the same) ---
@app.post("/data-fetcher/fetch-and-store-all-fixtures", status_code=200)
async def api_fetch_and_store_fixtures(
    data_source: IFootballDataSource = Depends(get_football_data_source_dependency),
):
    try:
        db = get_firestore_client()
        summary = await fetch_and_store_fixtures(
            db, data_source, days_ahead=settings.DEFAULT_LOOKOUT_WINDOW_DAYS
        )
        return summary
    # ... (error handling remains the same as previous version) ...
    except FixtureStorageError as e:
        logger.error(f"API: Error during fixture fetching/storage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        logger.critical(f"API: Service runtime error: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")
    except Exception as e:
        logger.error(f"API: Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"An unexpected internal error occurred: {str(e)}"
        )


# ... (Root and Health check endpoints remain the same) ...
@app.get("/")
async def read_root():
    return {
        "message": "Welcome to the Fixture Scout AI - Football Data Fetcher Service"
    }


@app.get("/health")
async def health_check():
    db_ok = False
    ds_ok = bool(_football_data_source_instance)
    try:
        get_firestore_client()
        db_ok = True
    except Exception:
        logger.warning(
            "Health check: Firestore client not healthy for DataFetcher service."
        )

    if db_ok and ds_ok:
        return {
            "status": "ok",
            "firestore_healthy": True,
            "data_source_initialized": True,
        }
    else:
        details = []
        if not db_ok:
            details.append("Firestore client issue.")
        if not ds_ok:
            details.append("Data source not initialized.")
        return {
            "status": "degraded",
            "firestore_healthy": db_ok,
            "data_source_initialized": ds_ok,
            "detail": " ".join(details) or "One or more components are not healthy.",
        }
