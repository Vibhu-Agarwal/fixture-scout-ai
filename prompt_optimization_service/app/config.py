# prompt_optimization_service/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Vertex AI Configuration (similar to Scout Service)
    GCP_PROJECT_ID: str | None = os.getenv("GCP_PROJECT_ID")
    GCP_REGION: str | None = os.getenv("GCP_REGION")  # Optional, depending on model
    # Model used for the optimization task itself
    OPTIMIZER_GEMINI_MODEL_NAME: str = os.getenv(
        "OPTIMIZER_GEMINI_MODEL_NAME", "gemini-1.5-flash"
    )  # Flash might be good for this task


settings = Settings()
