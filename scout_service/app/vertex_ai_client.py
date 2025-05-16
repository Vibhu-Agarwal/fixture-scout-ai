# scout_service/app/vertex_ai_client.py
import logging
import vertexai
from vertexai.generative_models import GenerativeModel
from .config import settings

logger = logging.getLogger(__name__)

gemini_model_instance = None


def get_vertex_ai_gemini_client():
    global gemini_model_instance
    if gemini_model_instance is None:
        try:
            if not settings.GCP_PROJECT_ID:
                raise ValueError(
                    "GCP_PROJECT_ID environment variable not set for Vertex AI."
                )

            if settings.GCP_REGION:
                vertexai.init(
                    project=settings.GCP_PROJECT_ID, location=settings.GCP_REGION
                )
                logger.info(
                    f"Vertex AI initialized for project '{settings.GCP_PROJECT_ID}' and location '{settings.GCP_REGION}'."
                )
            else:
                vertexai.init(project=settings.GCP_PROJECT_ID)
                logger.warning(
                    f"Vertex AI initialized for project '{settings.GCP_PROJECT_ID}' with no specific location (using global or model default)."
                )

            gemini_model_instance = GenerativeModel(settings.GEMINI_MODEL_NAME_VERTEX)
            logger.info(
                f"Vertex AI Gemini model '{settings.GEMINI_MODEL_NAME_VERTEX}' loaded."
            )
        except Exception as e:
            logger.error(
                f"Could not initialize Vertex AI Gemini client. Error: {e}",
                exc_info=True,
            )
            raise  # Re-raise to halt app startup if LLM is critical
    return gemini_model_instance
