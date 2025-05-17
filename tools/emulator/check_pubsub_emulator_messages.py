# check_emulator_messages.py
import os
import time
import json
from concurrent.futures import TimeoutError
from google.cloud import pubsub_v1
from dotenv import load_dotenv

# Load environment variables from a .env file in the same directory as the script
# (or the project root if you run the script from there)
load_dotenv()

# Configuration - A good practice to fetch from env vars
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
PUBSUB_EMULATOR_HOST = os.getenv("PUBSUB_EMULATOR_HOST")

# Topics you want to subscribe to
# These should match the TOPIC_IDs used by your publisher
TOPIC_IDS = [
    os.getenv("EMAIL_NOTIFICATIONS_TOPIC_ID", "email-notifications-topic"),
    os.getenv(
        "PHONE_MOCK_NOTIFICATIONS_TOPIC_ID", "mock-phone-call-notifications-topic"
    ),
    os.getenv(
        "NOTIFICATION_STATUS_UPDATE_TOPIC_ID", "notification-status-updates-topic"
    ),
    # Add any other topic IDs you might have
]

# --- Check for necessary configurations ---
if not GCP_PROJECT_ID:
    print("Error: GCP_PROJECT_ID environment variable not set.")
    print("Please set it in your .env file or environment.")
    exit(1)

if not PUBSUB_EMULATOR_HOST:
    print("Error: PUBSUB_EMULATOR_HOST environment variable not set.")
    print("This script is intended for use with the Pub/Sub emulator.")
    print("Please set it (e.g., 'localhost:8538') in your .env file or environment.")
    exit(1)

print(f"Attempting to connect to Pub/Sub emulator at: {PUBSUB_EMULATOR_HOST}")
print(f"Using GCP Project ID for topics/subscriptions: {GCP_PROJECT_ID}")
print(f"Subscribing to topics: {', '.join(TOPIC_IDS)}")
print("----------------------------------------------------")
print("Waiting for messages... Press Ctrl+C to exit.")
print("----------------------------------------------------")

# Create a subscriber client
# The client will automatically use the emulator if PUBSUB_EMULATOR_HOST is set
try:
    subscriber = pubsub_v1.SubscriberClient()
except Exception as e:
    print(f"Error creating Pub/Sub subscriber client: {e}")
    print("Ensure the emulator is running and PUBSUB_EMULATOR_HOST is correctly set.")
    exit(1)

# Keep track of subscription paths we've created for this run
# This is important because subscriptions are persistent in Pub/Sub (even the emulator)
# For a simple test script, we often create a new subscription each time and delete it on exit,
# or use a fixed name and let it be. For this script, let's create ephemeral ones.
subscription_paths = []

from google.cloud.pubsub_v1.subscriber.message import Message

from typing import Callable


def get_callback(subscription: str) -> Callable[["Message"], None]:
    return lambda message: callback(message, subscription)


def callback(message: Message, subscription: str) -> None:
    """
    Callback function to process received messages.
    """
    print(f"\n--- New Message Received ---")
    print(f"Subscription: {subscription}")  # The full subscription path

    try:
        print("Raw Message:", message)
        print("message.data:", message.data)
        data_str = message.data.decode("utf-8")
        data_dict = json.loads(data_str)
        print("Data (JSON Parsed):")
        print(json.dumps(data_dict, indent=2))
    except json.JSONDecodeError:
        print(f"Data (Raw UTF-8): {message.data.decode('utf-8')}")
    except UnicodeDecodeError:
        print(f"Data (Raw Bytes): {message.data}")

    if message.attributes:
        print("Attributes:")
        for key, value in message.attributes.items():
            print(f"  {key}: {value}")

    print(f"--------------------------")
    message.ack()  # Acknowledge the message so Pub/Sub doesn't redeliver it


try:
    for topic_id in TOPIC_IDS:
        topic_path = subscriber.topic_path(GCP_PROJECT_ID, topic_id)

        # Create a unique subscription name for each run to avoid conflicts
        # and ensure we get messages published *after* this script starts.
        # Subscriptions are persistent, so using a fixed name means you might
        # see old messages if the script crashed before acking.
        # A timestamp or UUID makes it unique for this run.
        subscription_id = f"{topic_id}-subscriber-script-{int(time.time())}"
        subscription_path = subscriber.subscription_path(
            GCP_PROJECT_ID, subscription_id
        )

        print(
            f"\nAttempting to create/use subscription '{subscription_path}' for topic '{topic_path}'..."
        )

        try:
            # Create the subscription. If it already exists (unlikely with unique name),
            # this might error, but for unique names, it should be fine.
            # For fixed names, you'd use get_subscription and create if not found.
            subscription = subscriber.create_subscription(
                request={"name": subscription_path, "topic": topic_path}
            )
            print(f"Subscription '{subscription.name}' created for topic '{topic_id}'.")
            subscription_paths.append(subscription_path)
        except (
            Exception
        ) as e_create_sub:  # Could be AlreadyExists if name wasn't unique
            print(
                f"Warning: Could not create subscription '{subscription_path}' (maybe it exists or topic issue?): {e_create_sub}"
            )
            # Try to use it anyway if it's an "AlreadyExists" type error, otherwise skip
            # For simplicity, if create fails with unique name, it's likely a problem.
            # If using a fixed name, you'd try get_subscription here.
            # For now, if create fails with unique name, something is wrong with topic or permissions.
            print(f"Skipping subscription to topic '{topic_id}' due to error.")
            continue

        # Start pulling messages
        # The `subscribe` method is non-blocking and returns a `StreamingPullFuture`.
        # The `callback` function will be called on a separate thread by the client library.
        streaming_pull_future = subscriber.subscribe(
            subscription_path, callback=get_callback(subscription_path)
        )
        print(f"Listening for messages on '{subscription_path}'...")

    # Keep the main thread alive to allow callbacks to run on their threads.
    # The `streaming_pull_future.result()` would block indefinitely.
    # We want to listen on multiple subscriptions.
    while True:
        time.sleep(60)  # Keep alive, or use future.result() if only one subscription
        # For multiple subscriptions, this loop just keeps the main thread from exiting.

except KeyboardInterrupt:
    print("\nShutting down subscriber script...")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    # Clean up: Delete the subscriptions we created for this run
    # This is good practice for ephemeral test subscriptions.
    if subscription_paths:
        print("Deleting ephemeral subscriptions...")
        for sub_path in subscription_paths:
            try:
                subscriber.delete_subscription(request={"subscription": sub_path})
                print(f"Deleted subscription: {sub_path}")
            except Exception as e_del:
                print(f"Failed to delete subscription {sub_path}: {e_del}")
    print("Exited.")
