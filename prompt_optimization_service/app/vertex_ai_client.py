# prompt_optimization_service/app/vertex_ai_client.py
import logging
import os
import vertexai
from vertexai.generative_models import GenerativeModel
from .config import settings

logger = logging.getLogger(__name__)
_optimizer_gemini_model_instance: GenerativeModel | None = None

def get_optimizer_gemini_client() -> GenerativeModel:
    global _optimizer_gemini_model_instance
    if _optimizer_gemini_model_instance is None:
        try:
            if not settings.GCP_PROJECT_ID:
                # For local dev with ADC user, project might be inferred if not explicitly set during vertexai.init()
                # but Vertex AI generally expects a project.
                # If running on Cloud Run, project is available from metadata server.
                logger.warning("GCP_PROJECT_ID not explicitly set for Vertex AI client initialization.")
            
            # Initialize Vertex AI. Location might be optional for some models or inferred.
            if settings.GCP_REGION:
                vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_REGION)
                logger.info(f"Optimizer Vertex AI initialized for project '{settings.GCP_PROJECT_ID}' and location '{settings.GCP_REGION}'.")
            else:
                vertexai.init(project=settings.GCP_PROJECT_ID)
                logger.info(f"Optimizer Vertex AI initialized for project '{settings.GCP_PROJECT_ID}' (no specific location).")

            _optimizer_gemini_model_instance = GenerativeModel(settings.OPTIMIZER_GEMINI_MODEL_NAME)
            logger.info(f"Optimizer Vertex AI Gemini model '{settings.OPTIMIZER_GEMINI_MODEL_NAME}' loaded.")
        except Exception as e:
            logger.error(f"Could not initialize Optimizer Vertex AI Gemini client. Error: {e}", exc_info=True)
            raise RuntimeError(f"Failed to initialize Optimizer Vertex AI Gemini client: {e}") # Fail fast
    return _optimizer_gemini_model_instance