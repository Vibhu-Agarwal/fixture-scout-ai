# scout_service/app/utils/logging_config.py
import logging
import os
import sys


def setup_logging():
    """
    Configures basic logging for the application.
    Logs to stdout, which is suitable for Cloud Run and other containerized environments.
    """
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Basic configuration for console logging
    # Cloud Run typically captures stdout/stderr, so a simple stream handler is often sufficient.
    # More complex handlers (e.g., JSON logging) can be added if needed.
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,  # Explicitly set to stdout
    )
    # You can also adjust logging levels for specific libraries if they are too verbose
    # logging.getLogger("google.api_core").setLevel(logging.WARNING)
    # logging.getLogger("google.auth").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {log_level_str}")


# Call setup_logging when this module is imported, or call it explicitly in main.py
# For simplicity, we can call it once at the start of the application.
