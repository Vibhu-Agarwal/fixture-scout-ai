import logging
import datetime

from google.cloud import firestore

from ..config import settings

logger = logging.getLogger(__name__)


def delete_future_reminders(db: firestore.Client):
    """Deletes documents from the 'reminders' collection where the
    'kickoff_time_utc' timestamp is in the future.

    This function queries for all reminders scheduled after the current
    time and deletes them in batches of 500 for efficiency.

    Args:
        db: An authenticated firestore.Client instance.
    """
    # Get the current time in UTC to ensure a correct comparison
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    logger.info(f"Current time (UTC): {now_utc}")
    logger.info("Querying for reminders with a kickoff_time_utc greater than now...")

    # Reference the collection and create the query
    reminders_ref = db.collection("reminders")
    query = reminders_ref.where(
        field_path="kickoff_time_utc", op_string=">", value=now_utc
    )

    # A batch can hold a maximum of 500 operations
    batch = db.batch()
    docs_stream = query.stream()
    docs_in_batch = 0
    total_deleted = 0

    for doc in docs_stream:
        # Add the delete operation to the batch
        batch.delete(doc.reference)
        docs_in_batch += 1
        total_deleted += 1

        # When the batch is full, commit it and start a new one
        if docs_in_batch == 500:
            logger.info(f"Committing a full batch of {docs_in_batch} documents...")
            batch.commit()
            # Reset for the next batch
            batch = db.batch()
            docs_in_batch = 0

    # Commit the final batch if it has any documents left
    if docs_in_batch > 0:
        logger.info(f"Committing the final batch of {docs_in_batch} documents...")
        batch.commit()

    if total_deleted == 0:
        logger.info("No future reminders found to delete.")
    else:
        logger.info(f"Successfully deleted a total of {total_deleted} documents.")
