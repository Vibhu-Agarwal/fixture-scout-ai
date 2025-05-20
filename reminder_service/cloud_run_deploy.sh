#!/usr/bin/env bash
set -e

# --- Configuration ---
export SERVICE_VERSION="0.2.0" # Match your reminder_service/app/main.py version
export SERVICE_NAME="reminder-service"
export GCP_PROJECT_ID_VAR=$(gcloud config get-value project)
if [ -z "$GCP_PROJECT_ID_VAR" ]; then
    echo "GCP_PROJECT_ID is not set. Please set it using 'gcloud config set project YOUR_PROJECT_ID'"
    exit 1
fi
export REGION="asia-south1" # CHANGE THIS TO YOUR PREFERRED REGION
export AR_REPO_NAME="fixture-scout-images"
export FIRESTORE_DATABASE_NAME="fixture-scout-ai-db" # Ensure this is correct

# Pub/Sub Topic IDs this service INTERACTS with
# Topics it PUBLISHES to (for scheduler part)
export EMAIL_NOTIFICATIONS_TOPIC_ID="email-notifications-topic"
export PHONE_MOCK_NOTIFICATIONS_TOPIC_ID="mock-phone-call-notifications-topic"
# Topic it ensures exists because it will have a SUBSCRIPTION to it (for status updater part)
export NOTIFICATION_STATUS_UPDATE_TOPIC_ID_TO_SUBSCRIBE="notification-status-updates-topic"


export IMAGE_TAG_NAME="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID_VAR}/${AR_REPO_NAME}/${SERVICE_NAME}:${SERVICE_VERSION}"

echo "--- Deployment Configuration for ${SERVICE_NAME} ---"
echo "Service Version: ${SERVICE_VERSION}"
echo "GCP Project ID: ${GCP_PROJECT_ID_VAR}"
echo "Region: ${REGION}"
echo "Image Tag: ${IMAGE_TAG_NAME}"
echo "Firestore DB Name: ${FIRESTORE_DATABASE_NAME}"
echo "Email Topic ID: ${EMAIL_NOTIFICATIONS_TOPIC_ID}"
echo "Phone Mock Topic ID: ${PHONE_MOCK_NOTIFICATIONS_TOPIC_ID}"
echo "Status Update Topic ID (to subscribe to): ${NOTIFICATION_STATUS_UPDATE_TOPIC_ID_TO_SUBSCRIBE}"
echo "----------------------------------------------------"

echo "Deploying ${SERVICE_NAME} to Cloud Run..."

# For this service:
# - /scheduler/check-and-dispatch-reminders: Called by Cloud Scheduler (needs to be invokable, ideally OIDC authenticated).
# - /reminders/handle-status-update: Called by Pub/Sub push (needs to be invokable, ideally OIDC authenticated from Pub/Sub).
# Keeping --allow-unauthenticated for initial deployment and testing of these triggers.
# We will secure these when setting up Cloud Scheduler and Pub/Sub push subscriptions.

gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_TAG_NAME}" \
    --source=. \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID_VAR}" \
    --set-env-vars="FIRESTORE_DATABASE_NAME=${FIRESTORE_DATABASE_NAME}" \
    --set-env-vars="LOG_LEVEL=INFO" \
    --set-env-vars="EMAIL_NOTIFICATIONS_TOPIC_ID=${EMAIL_NOTIFICATIONS_TOPIC_ID}" \
    --set-env-vars="PHONE_MOCK_NOTIFICATIONS_TOPIC_ID=${PHONE_MOCK_NOTIFICATIONS_TOPIC_ID}" \
    --set-env-vars="NOTIFICATION_STATUS_UPDATE_TOPIC_ID_TO_SUBSCRIBE=${NOTIFICATION_STATUS_UPDATE_TOPIC_ID_TO_SUBSCRIBE}" \
    --timeout=300s \
    --concurrency=100 # Can handle some concurrent scheduler hits or Pub/Sub pushes
    --min-instances=0 \
    --max-instances=2 # Start low, adjust based on load
    # Service account for this service will need:
    # - Cloud Datastore User (for Firestore read/write)
    # - Pub/Sub Publisher (to publish to notification topics)
    # - Pub/Sub Subscriber (implicitly, to receive pushes, but main permission is invoker for the endpoint)
    # - Logs Writer

echo "----------------------------------------------------"
echo "Deployment of ${SERVICE_NAME} initiated."
echo "Service URL will be outputted by gcloud. Note it down for Cloud Scheduler and Pub/Sub Push Subscription setup."
echo "The runtime service account for '${SERVICE_NAME}' will need 'Cloud Datastore User' and 'Pub/Sub Publisher' roles."
echo "It will also need to be invokable by Cloud Scheduler and Pub/Sub (e.g. 'Cloud Run Invoker' for specific invokers)."
echo "----------------------------------------------------"