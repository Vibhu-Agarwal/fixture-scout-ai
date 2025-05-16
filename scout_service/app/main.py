# scout_service/app/main.py
import logging
import asyncio
from fastapi import FastAPI, HTTPException, Body, Depends
import httpx

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
from .vertex_ai_client import get_vertex_ai_gemini_client
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Scout Service",
    description="Processes fixtures using an LLM (Gemini via Vertex AI) to create personalized reminders.",
    version="0.1.1",
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


async def _trigger_user_processing_task(
    client: httpx.AsyncClient, user_id: str, base_url: str
) -> tuple[str, bool, str]:
    """
    Triggers processing for a single user and returns status.
    Returns: (user_id, success_status, message_or_error)
    """
    logger.info(f"Orchestrator Task: Triggering processing for user_id: {user_id}")
    processing_url = f"{base_url}/scout/process-user-fixtures"
    try:
        response = await client.post(
            processing_url, json={"user_id": user_id}, timeout=60.0
        )  # Increased timeout for individual processing

        if response.status_code == 200:
            logger.info(
                f"Orchestrator Task: Successfully triggered processing for user {user_id}. Response: {response.json()}"
            )
            return (
                user_id,
                True,
                f"Successfully processed. LLM Summary: {response.json().get('message', 'OK')}",
            )
        else:
            error_detail = response.text
            logger.error(
                f"Orchestrator Task: Failed to trigger processing for user {user_id}. Status: {response.status_code}, Response: {error_detail}"
            )
            return (
                user_id,
                False,
                f"Failed. Status: {response.status_code}, Detail: {error_detail[:200]}",
            )  # Truncate long errors
    except httpx.TimeoutException:
        logger.error(
            f"Orchestrator Task: Timeout while triggering processing for user {user_id} at {processing_url}",
            exc_info=True,
        )
        return user_id, False, "Failed due to timeout."
    except httpx.RequestError as e:
        logger.error(
            f"Orchestrator Task: HTTP request error for user {user_id}: {e}",
            exc_info=True,
        )
        return user_id, False, f"Failed due to HTTP request error: {str(e)}"
    except Exception as e:
        logger.error(
            f"Orchestrator Task: Unexpected error for user {user_id}: {e}",
            exc_info=True,
        )
        return user_id, False, f"Failed due to unexpected error: {str(e)}"


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

        # Use a shared httpx.AsyncClient for connection pooling
        # SCOUT_SERVICE_INTERNAL_URL needs to be set in your environment.
        # e.g., in .env: SCOUT_SERVICE_INTERNAL_URL="http://localhost:8002"
        # OR on Cloud Run: set as an environment variable for the service
        # (often the service URL itself if it's publicly invokable, or internal DNS if available)
        base_url = settings.SCOUT_SERVICE_INTERNAL_URL
        if not base_url:
            logger.error(
                "SCOUT_SERVICE_INTERNAL_URL environment variable is not set. Cannot proceed with orchestration."
            )
            raise HTTPException(
                status_code=500, detail="Orchestration service URL not configured."
            )

        # Use a semaphore to limit concurrency if needed, e.g., if the downstream service has limits
        # or to prevent overwhelming the current service if it's making many outbound calls.
        # For now, let's allow all to run, but this is a point for future tuning.
        # CONCURRENCY_LIMIT = 10 # Example limit
        # semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        # async def _throttled_trigger_user_processing_task(*args, **kwargs):
        #     async with semaphore:
        #         return await _trigger_user_processing_task(*args, **kwargs)

        async with httpx.AsyncClient() as client:
            tasks = [
                _trigger_user_processing_task(client, user_id, base_url)
                for user_id in users_to_process_ids
            ]
            # tasks = [
            #    _throttled_trigger_user_processing_task(client, user_id, base_url)
            #    for user_id in users_to_process_ids
            # ] # If using semaphore

            results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_users_count = 0
        failed_users_count = 0
        detailed_results = []

        for i, result in enumerate(results):
            user_id_processed = users_to_process_ids[
                i
            ]  # Get user_id based on original order
            if isinstance(result, Exception):
                logger.error(
                    f"Orchestration: Exception for user {user_id_processed}: {result}",
                    exc_info=result,
                )
                failed_users_count += 1
                detailed_results.append(
                    {
                        "user_id": user_id_processed,
                        "status": "failed",
                        "detail": f"Exception: {str(result)}",
                    }
                )
            elif isinstance(result, tuple) and len(result) == 3:
                _, success, message = result  # result is (user_id, success, message)
                if success:
                    processed_users_count += 1
                    detailed_results.append(
                        {
                            "user_id": user_id_processed,
                            "status": "success",
                            "detail": message,
                        }
                    )
                else:
                    failed_users_count += 1
                    detailed_results.append(
                        {
                            "user_id": user_id_processed,
                            "status": "failed",
                            "detail": message,
                        }
                    )
            else:  # Should not happen if _trigger_user_processing_task is correct
                logger.error(
                    f"Orchestration: Unexpected result format for user {user_id_processed}: {result}"
                )
                failed_users_count += 1
                detailed_results.append(
                    {
                        "user_id": user_id_processed,
                        "status": "failed",
                        "detail": "Unexpected result format from task.",
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
            "successful_triggers": processed_users_count,
            "failed_triggers": failed_users_count,
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
        llm = get_vertex_ai_gemini_client()
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
