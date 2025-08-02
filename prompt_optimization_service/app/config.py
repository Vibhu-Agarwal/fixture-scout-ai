# prompt_optimization_service/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    GCP_PROJECT_ID: str | None = os.getenv("GOOGLE_CLOUD_PROJECT")
    GCP_REGION: str | None = os.getenv("GOOGLE_CLOUD_LOCATION")

    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    LLM_MAX_OUTPUT_TOKENS: int = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "512"))

    # Model used for the optimization task itself
    OPTIMIZER_GEMINI_MODEL_NAME: str = os.getenv(
        "OPTIMIZER_GEMINI_MODEL_NAME", "gemini-2.5-flash"
    )


settings = Settings()
