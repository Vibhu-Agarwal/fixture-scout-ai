# scout_service/app/main.py
import logging
from fastapi import FastAPI, HTTPException, Body, Depends

# Important: Setup logging as early as possible
from .utils.logging_config import setup_logging

setup_logging()  # Initialize logging configuration

from .config import settings  # Import after logging is set up
from .models import ScoutRequest
from .services.reminder_processing_service import (
    process_fixtures_for_user,
    ReminderProcessingError,
    LLMResponseError,
)

from .firestore_client import get_firestore_client
from .vertex_ai_client import get_vertex_ai_gemini_client
from contextlib import asynccontextmanager


logger = logging.getLogger(__name__)

app = FastAPI(
    title="Scout Service",
    description="Processes fixtures using an LLM (Gemini via Vertex AI) to create personalized reminders.",
    version="0.1.1",  # Incremented version
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Scout Service starting up...")
    try:
        get_firestore_client()
        get_vertex_ai_gemini_client()
        logger.info(
            "Firestore and Vertex AI clients initialized successfully on startup."
        )
    except Exception as e:
        logger.critical(f"Failed to initialize clients on startup: {e}", exc_info=True)
    yield


app.router.lifespan_context = lifespan


@app.post("/scout/process-user-fixtures", status_code=200)
async def api_process_user_fixtures(request: ScoutRequest = Body(...)):
    """
    API endpoint to trigger fixture processing for a user.
    """
    try:
        logger.info(
            f"Received request to process fixtures for user_id: {request.user_id}"
        )
        result_summary = await process_fixtures_for_user(request.user_id)
        return result_summary
    except LLMResponseError as e:
        logger.error(
            f"LLM processing error for user {request.user_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=502, detail=f"Error interacting with LLM: {str(e)}"
        )  # Bad Gateway
    except ReminderProcessingError as e:
        logger.error(
            f"Reminder processing error for user {request.user_id}: {e}", exc_info=True
        )
        if (
            "not found" in str(e).lower() or "missing" in str(e).lower()
        ):  # Specific check for 404 type errors
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error during processing: {str(e)}",
            )
    except Exception as e:
        logger.error(
            f"Unexpected error processing fixtures for user {request.user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"An unexpected internal error occurred: {str(e)}"
        )


@app.get("/")
async def read_root():
    return {
        "message": f"Welcome to the Fixture Scout AI - Scout Service (v{app.version}, Vertex AI)"
    }


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    # Check if clients are available (simple check)
    # A more thorough health check might try a small operation (e.g., read a dummy doc from Firestore)
    try:
        db = get_firestore_client()
        llm = get_vertex_ai_gemini_client()
        if db and llm:  # Basic check they are not None
            return {
                "status": "ok",
                "firestore_initialized": True,
                "vertex_ai_initialized": True,
            }
        else:
            return {
                "status": "degraded",
                "firestore_initialized": bool(db),
                "vertex_ai_initialized": bool(llm),
            }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}
