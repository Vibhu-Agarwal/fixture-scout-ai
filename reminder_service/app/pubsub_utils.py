# reminder_scheduler_service/app/pubsub_utils.py
import logging
import json
from typing import Dict
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.publisher.exceptions import MessageTooLargeError
from google.api_core.exceptions import NotFound as PubSubTopicNotFound, AlreadyExists

from .config import settings  # Assuming settings are accessible here

logger = logging.getLogger(__name__)

# This global client will be initialized by main.py's lifespan manager
# and passed to functions here, or these functions can fetch it.
# For now, let's assume it's passed or fetched via a getter.
# A better approach might be for these functions to accept the client as an argument.


async def ensure_pubsub_topic_exists(
    publisher: pubsub_v1.PublisherClient, project_id: str, topic_id: str
):
    """Ensures a Pub/Sub topic exists, creating it if necessary."""
    logger.info(f"Ensuring Pub/Sub topic '{topic_id}' exists under {project_id}...")
    if not project_id:  # Guard against missing project_id
        logger.error(
            f"Cannot ensure topic '{topic_id}' exists without a GCP_PROJECT_ID."
        )
        raise ValueError(
            f"GCP_PROJECT_ID is required to ensure topic '{topic_id}' existence."
        )

    topic_path = publisher.topic_path(project_id, topic_id)
    try:
        publisher.get_topic(topic=topic_path)
        logger.info(f"Pub/Sub topic '{topic_path}' already exists.")
    except PubSubTopicNotFound:
        logger.info(f"Pub/Sub topic '{topic_path}' not found. Creating it...")
        try:
            publisher.create_topic(name=topic_path)
            logger.info(f"Pub/Sub topic '{topic_path}' created successfully.")
        except AlreadyExists:
            logger.info(
                f"Pub/Sub topic '{topic_path}' was created by another process concurrently."
            )
        except Exception as e_create:
            logger.error(
                f"Failed to create Pub/Sub topic '{topic_path}': {e_create}",
                exc_info=True,
            )
            raise
    except Exception as e_get:
        logger.error(
            f"Failed to check existence of Pub/Sub topic '{topic_path}': {e_get}",
            exc_info=True,
        )
        raise


async def publish_to_pubsub(
    publisher: pubsub_v1.PublisherClient, project_id: str, topic_id: str, data: Dict
) -> bool:
    """
    Publishes a message to the specified Pub/Sub topic.
    Returns True if publishing was successful, False otherwise.
    """
    if not project_id:
        logger.error(f"Cannot publish to topic '{topic_id}' without a GCP_PROJECT_ID.")
        return False  # Or raise an error

    topic_path = publisher.topic_path(project_id, topic_id)
    message_json = json.dumps(data)
    message_bytes = message_json.encode("utf-8")

    logger.debug(
        f"Publishing to Pub/Sub topic: {topic_path}, Data for original_reminder_id: {data.get('original_reminder_id')}"
    )
    try:
        publish_future = publisher.publish(topic_path, message_bytes)
        # Using a timeout is good practice for future.result()
        publish_future.result(timeout=30.0)  # Wait for publish with timeout
        logger.info(
            f"Successfully published message for reminder_id {data.get('original_reminder_id')} to topic {topic_id}."
        )
        return True
    except MessageTooLargeError:
        logger.error(
            f"Message for reminder {data.get('original_reminder_id')} is too large for Pub/Sub topic {topic_id}.",
            exc_info=True,
        )
        return False
    except PubSubTopicNotFound:
        logger.error(
            f"Pub/Sub topic {topic_path} not found. Ensure it is created in project '{project_id}'.",
            exc_info=True,
        )
        return False
    except TimeoutError:  # from publish_future.result(timeout=...)
        logger.error(
            f"Timeout publishing message for reminder {data.get('original_reminder_id')} to topic {topic_id}.",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"Failed to publish message for reminder {data.get('original_reminder_id')} to topic {topic_id}: {e}",
            exc_info=True,
        )
        return False
