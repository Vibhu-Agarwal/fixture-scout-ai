# scout_service/app/main.py
import logging
import asyncio
from fastapi import FastAPI, HTTPException, Body

from .utils.logging_config import setup_logging

setup_logging()

from .config import settings
from .models import ScoutRequest
from .services.reminder_processing_service import (
    process_fixtures_for_user,
    ReminderProcessingError,
    LLMResponseError,
)
from .firestore_client import get_firestore_client
from .vertex_ai_client import get_vertex_ai_genai_client
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Scout Service",
    description="Processes fixtures using an LLM (Gemini via Vertex AI) to create personalized reminders.",
    version="0.2.0",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Scout Service starting up...")
    try:
        get_firestore_client()
        get_vertex_ai_genai_client()
        logger.info(
            "Firestore and Vertex AI GenAI clients initialized successfully on startup."
        )
    except Exception as e:
        logger.critical(f"Failed to initialize clients on startup: {e}", exc_info=True)
        raise
    yield


app.router.lifespan_context = lifespan


# --- Main API Endpoints ---
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
        )
    except ReminderProcessingError as e:
        logger.error(
            f"Reminder processing error for user {request.user_id}: {e}", exc_info=True
        )
        if "not found" in str(e).lower() or "missing" in str(e).lower():
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


@app.post("/scout/orchestrate-all-user-processing", status_code=200)
async def orchestrate_all_user_processing():
    """
    Orchestrates the fixture processing for all users.
    Fetches all user_ids with preferences and triggers individual processing for each.
    This endpoint is intended to be called by Cloud Scheduler.
    """
    logger.info(
        "Concurrent Orchestration triggered: Processing fixtures for all users."
    )
    db = get_firestore_client()
    users_to_process_ids = []

    try:
        preferences_query = db.collection(settings.USER_PREFERENCES_COLLECTION).stream()
        for pref_snap in preferences_query:
            users_to_process_ids.append(pref_snap.id)

        logger.info(
            f"Found {len(users_to_process_ids)} users with preferences to process."
        )

        if not users_to_process_ids:
            logger.info("No users found with preferences. Orchestration complete.")
            return {"message": "No users with preferences to process.", "results": []}

        # Create asyncio tasks to call the service logic function directly
        tasks = [process_fixtures_for_user(user_id) for user_id in users_to_process_ids]

        results_from_service = await asyncio.gather(*tasks, return_exceptions=True)

        processed_users_count = 0
        failed_users_count = 0
        detailed_results = []

        for i, result_or_exception in enumerate(results_from_service):
            user_id_processed = users_to_process_ids[i]
            if isinstance(result_or_exception, BaseException):
                logger.error(
                    f"Orchestration: Exception processing user {user_id_processed}: {result_or_exception}",
                    exc_info=result_or_exception,
                )
                failed_users_count += 1
                detailed_results.append(
                    {
                        "user_id": user_id_processed,
                        "status": "failed",
                        "detail": f"Exception: {str(result_or_exception)}",
                    }
                )
            else:
                logger.info(
                    f"Orchestration: Successfully processed user {user_id_processed}. Result: {result_or_exception}"
                )
                processed_users_count += 1
                detailed_results.append(
                    {
                        "user_id": user_id_processed,
                        "status": "success",
                        "detail": result_or_exception.get(
                            "message", "OK"
                        ),  # Or other relevant info from the dict
                        "reminders_created": result_or_exception.get(
                            "reminders_created", 0
                        ),
                    }
                )

        summary_message = (
            f"Concurrent Orchestration complete. "
            f"Users successfully processed: {processed_users_count}. "
            f"Users failed or had errors: {failed_users_count}."
        )
        logger.info(summary_message)
        return {
            "message": summary_message,
            "total_processed_attempts": len(users_to_process_ids),
            "successful_processing": processed_users_count,
            "failed_processing": failed_users_count,
            "results": detailed_results,
        }

    except Exception as e:
        logger.error(
            f"Critical error during concurrent orchestration: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")


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
        llm = get_vertex_ai_genai_client()
        if db and llm:
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
