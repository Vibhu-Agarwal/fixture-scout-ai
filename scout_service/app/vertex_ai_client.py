# scout_service/app/vertex_ai_client.py
import logging
from google import genai
from .config import settings

logger = logging.getLogger(__name__)
_genai_client = None


def get_vertex_ai_genai_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        try:
            if not settings.GCP_PROJECT_ID:
                raise ValueError(
                    "GOOGLE_CLOUD_PROJECT environment variable not set for Vertex AI GenAI client."
                )
            _genai_client = genai.Client(vertexai=True, location="global")
            logger.info("Vertex AI GenAI client initialized successfully.")
        except Exception as e:
            logger.error(
                f"Could not initialize Vertex AI GenAI client. Error: {e}",
                exc_info=True,
            )
            raise
    return _genai_client
