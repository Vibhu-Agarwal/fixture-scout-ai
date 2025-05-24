# prompt_optimization_service/app/main.py
import logging
import os
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Body, status as http_status
from fastapi.security import OAuth2PasswordBearer
from contextlib import asynccontextmanager

from .utils.logging_config import setup_logging

setup_logging()

from .config import settings
from .vertex_ai_client import get_optimizer_gemini_client  # Import the specific client
from .models import PromptOptimizeRequest, PromptOptimizeResponse, TokenData
from .services.optimization_logic import optimize_user_prompt, OptimizationError
from firebase_admin import auth as firebase_auth, exceptions as firebase_exceptions

logger = logging.getLogger(__name__)

_optimizer_model_client = None  # Will be initialized in lifespan


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> TokenData:
    credentials_exception = HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate Firebase credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        firebase_uid = decoded_token.get("uid")
        if not firebase_uid:
            raise credentials_exception
        logger.debug(f"Firebase ID Token validated for Firebase UID: {firebase_uid}")
        return TokenData(
            user_id=firebase_uid
        )  # Storing Firebase UID in user_id field of TokenData
    except firebase_exceptions.FirebaseError as e:
        logger.warning(f"Firebase ID Token verification failed: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(
            f"Unexpected error during Firebase token verification: {e}", exc_info=True
        )
        raise credentials_exception


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _optimizer_model_client
    logger.info("Prompt Optimization Service starting up...")
    try:
        _optimizer_model_client = (
            get_optimizer_gemini_client()
        )  # Initialize Vertex AI client
        logger.info("Optimizer Vertex AI client initialized successfully on startup.")
    except Exception as e:
        logger.critical(
            f"Failed to initialize Optimizer Vertex AI client on startup: {e}",
            exc_info=True,
        )
        # Decide if app should exit or continue in a degraded state
    yield
    logger.info("Prompt Optimization Service shutting down...")


app = FastAPI(
    title="Prompt Optimization Service",
    description="Optimizes user's natural language prompts for the Fixture Scout AI.",
    version="0.2.0",
    lifespan=lifespan,
)


@app.post("/prompts/optimize", response_model=PromptOptimizeResponse)
async def api_optimize_prompt(
    request_data: PromptOptimizeRequest = Body(...),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Receives a raw user prompt and returns an optimized version using an LLM.
    """
    if not _optimizer_model_client:  # Should have been initialized by lifespan
        logger.error("API: Optimizer model client not available.")
        raise HTTPException(
            status_code=503, detail="Optimization service is not ready."
        )

    try:
        logger.info(
            f"API: Received prompt optimization request for user_id: {current_user.user_id}"
        )
        optimized_text = await optimize_user_prompt(
            _optimizer_model_client, current_user.user_id, request_data
        )

        if not optimized_text.strip():  # If LLM returns empty string after stripping
            logger.warning(
                f"API: Optimization resulted in an empty prompt for user_id: {current_user.user_id}. Returning original."
            )
            # Fallback: return original prompt if optimization fails or is empty
            # Or, you could return an error or a specific message.
            # For now, if optimization fails to produce, the UI will just show the raw prompt as "optimized".
            # A better UX might be for this service to indicate failure more clearly.
            # Let's make the service return the original if optimization is empty,
            # but the client (UI) should be aware of this possibility.
            # For robustness, if optimization_logic raises an error, we catch it below.
            # If it returns empty, we can decide the behavior.
            # Let's assume for now `optimize_user_prompt` returns a non-empty string or raises an error.

        return PromptOptimizeResponse(
            raw_user_prompt=request_data.raw_user_prompt,
            optimized_user_prompt=optimized_text,
            model_used=settings.OPTIMIZER_GEMINI_MODEL_NAME,
        )
    except OptimizationError as e:
        logger.error(
            f"API: Optimization failed for user_id {current_user.user_id}: {e}",
            exc_info=True,
        )
        # Return the original prompt in case of optimization failure,
        # so the UI can still display something.
        # The UI should ideally indicate that optimization failed.
        # Alternatively, raise HTTPException(status_code=500, detail=str(e))
        return PromptOptimizeResponse(
            raw_user_prompt=request_data.raw_user_prompt,
            optimized_user_prompt=request_data.raw_user_prompt,  # Fallback
            model_used=f"fallback_due_to_error_with_{settings.OPTIMIZER_GEMINI_MODEL_NAME}",
        )
    except Exception as e:
        logger.error(
            f"API: Unexpected error during prompt optimization for user_id {current_user.user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred during prompt optimization.",
        )


@app.get("/")
async def read_root():
    return {"message": "Welcome to Fixture Scout AI's Prompt Optimization Service"}


@app.get("/health")
async def health_check():
    optimizer_model_ok = bool(_optimizer_model_client)
    if optimizer_model_ok:
        return {"status": "ok", "optimizer_model_initialized": True}
    else:
        return {
            "status": "degraded",
            "optimizer_model_initialized": False,
            "detail": "Optimizer LLM client not initialized.",
        }
