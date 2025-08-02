# prompt_optimization_service/app/vertex_ai_client.py
import logging
from google import genai
from .config import settings

logger = logging.getLogger(__name__)
_optimizer_client: genai.Client | None = None


def get_optimizer_genai_client() -> genai.Client:
    global _optimizer_client
    if _optimizer_client is None:
        try:
            if (not settings.GCP_PROJECT_ID) or (not settings.GCP_REGION):
                raise ValueError(
                    "GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION must be set in the environment variables."
                )
            _optimizer_client = genai.Client(vertexai=True)
            logger.info(f"Optimizer Vertex AI GenAI client initialized successfully.")
        except Exception as e:
            logger.error(
                f"Could not initialize Optimizer Vertex AI GenAI client. Error: {e}",
                exc_info=True,
            )
            raise
    return _optimizer_client
