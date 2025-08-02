# prompt_optimization_service/app/main.py
import base64
import json
import logging
import os
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Body, Header, status as http_status
from fastapi.security import OAuth2PasswordBearer
from contextlib import asynccontextmanager

from .utils.logging_config import setup_logging

setup_logging()

from .config import settings
from .vertex_ai_client import get_optimizer_genai_client  # Import the specific client
from .models import PromptOptimizeRequest, PromptOptimizeResponse, TokenData
from .services.optimization_logic import optimize_user_prompt, OptimizationError
from firebase_admin import auth as firebase_auth, exceptions as firebase_exceptions

logger = logging.getLogger(__name__)

_optimizer_genai_client = None  # Will be initialized in lifespan


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


async def get_current_user(
    x_endpoint_api_userinfo: Annotated[
        str | None, Header(convert_underscores=True)
    ] = None,
) -> TokenData:
    """
    Dependency to get user information passed by the ESPv2 gateway
    in the X-Endpoint-API-UserInfo header after Firebase Auth validation.
    """
    credentials_exception = HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED,
        detail="User not authenticated by API Gateway",
    )
    if x_endpoint_api_userinfo is None:
        logger.warning(
            "X-Endpoint-API-UserInfo header missing from request (ESPv2 should provide this)."
        )
        raise credentials_exception

    try:
        decoded_userinfo_str = x_endpoint_api_userinfo

        # Calculate required padding
        missing_padding = len(decoded_userinfo_str) % 4
        if missing_padding:
            decoded_userinfo_str += "=" * (4 - missing_padding)
            logger.debug(
                f"Added padding to X-Endpoint-API-UserInfo. Original length: {len(x_endpoint_api_userinfo)}, New length: {len(decoded_userinfo_str)}"
            )

        userinfo_json_bytes = base64.urlsafe_b64decode(decoded_userinfo_str)
        userinfo_json_str = userinfo_json_bytes.decode("utf-8")
        userinfo = json.loads(userinfo_json_str)

        # ESPv2 passes Firebase UID in 'id' field, email in 'email' field.
        # (Verify the exact field names ESPv2 uses for Firebase claims)
        # Common claims passed by ESPv2 after Firebase Auth: 'id' (Firebase UID), 'email', 'issuer'.
        firebase_uid = userinfo.get("user_id")
        email = userinfo.get("email")

        if not firebase_uid:
            logger.error(
                f"Firebase UID ('id' or 'user_id') not found in X-Endpoint-API-UserInfo: {userinfo}"
            )
            raise credentials_exception

        logger.debug(f"Authenticated user from Gateway (Firebase UID): {firebase_uid}")

        return TokenData(user_id=firebase_uid)
    except Exception as e:
        logger.error(
            f"Error decoding/parsing X-Endpoint-API-UserInfo header: {e}", exc_info=True
        )
        raise credentials_exception


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _optimizer_genai_client
    logger.info("Prompt Optimization Service starting up...")
    try:
        _optimizer_genai_client = get_optimizer_genai_client()
        logger.info("Optimizer Vertex AI client initialized successfully on startup.")
    except Exception as e:
        logger.critical(
            f"Failed to initialize Optimizer Vertex AI client on startup: {e}",
            exc_info=True,
        )
        raise
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
    if not _optimizer_genai_client:  # Should have been initialized by lifespan
        logger.error("API: Optimizer model client not available.")
        raise HTTPException(
            status_code=503, detail="Optimization service is not ready."
        )

    try:
        logger.info(
            f"API: Received prompt optimization request for user_id: {current_user.user_id}"
        )
        optimized_text = await optimize_user_prompt(
            _optimizer_genai_client, current_user.user_id, request_data
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
            optimized_user_prompt=request_data.raw_user_prompt,
            model_used=settings.OPTIMIZER_GEMINI_MODEL_NAME,
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
    optimizer_model_ok = bool(_optimizer_genai_client)
    if optimizer_model_ok:
        return {"status": "ok", "optimizer_model_initialized": True}
    else:
        return {
            "status": "degraded",
            "optimizer_model_initialized": False,
            "detail": "Optimizer LLM client not initialized.",
        }
