#!/usr/bin/env bash
set -e

# --- Configuration ---
export SERVICE_VERSION="0.1.0" # Match your notification_service/app/main.py version
export SERVICE_NAME="notification-service"
export GCP_PROJECT_ID_VAR=$(gcloud config get-value project)
if [ -z "$GCP_PROJECT_ID_VAR" ]; then
    echo "GCP_PROJECT_ID is not set. Please set it using 'gcloud config set project YOUR_PROJECT_ID'"
    exit 1
fi
export REGION="asia-south1" # CHANGE THIS TO YOUR PREFERRED REGION
export AR_REPO_NAME="fixture-scout-images"
export FIRESTORE_DATABASE_NAME="fixture-scout-ai-db" # Ensure this is correct

# Firestore Collection for logging notification attempts
export NOTIFICATION_LOG_COLLECTION="notification_log"

# Pub/Sub Topic ID this service PUBLISHES status updates TO
export NOTIFICATION_STATUS_UPDATE_TOPIC_ID="notification-status-updates-topic"


export IMAGE_TAG_NAME="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID_VAR}/${AR_REPO_NAME}/${SERVICE_NAME}:${SERVICE_VERSION}"

echo "--- Deployment Configuration for ${SERVICE_NAME} ---"
echo "Service Version: ${SERVICE_VERSION}"
echo "GCP Project ID: ${GCP_PROJECT_ID_VAR}"
echo "Region: ${REGION}"
echo "Image Tag: ${IMAGE_TAG_NAME}"
echo "Firestore DB Name: ${FIRESTORE_DATABASE_NAME}"
echo "Notification Log Collection: ${NOTIFICATION_LOG_COLLECTION}"
echo "Status Update Topic ID (to publish to): ${NOTIFICATION_STATUS_UPDATE_TOPIC_ID}"
echo "----------------------------------------------------"

echo "Deploying ${SERVICE_NAME} to Cloud Run..."

# For this service, its endpoints (/notifications/handle/email, /notifications/handle/phone-mock)
# are called by Pub/Sub push subscriptions.
# Keeping --allow-unauthenticated for initial deployment and testing of these triggers.
# We will secure these when setting up the Pub/Sub push subscriptions properly.

gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_TAG_NAME}" \
    --source=. \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID_VAR}" \
    --set-env-vars="FIRESTORE_DATABASE_NAME=${FIRESTORE_DATABASE_NAME}" \
    --set-env-vars="LOG_LEVEL=INFO" \
    --set-env-vars="NOTIFICATION_LOG_COLLECTION=${NOTIFICATION_LOG_COLLECTION}" \
    --set-env-vars="NOTIFICATION_STATUS_UPDATE_TOPIC_ID=${NOTIFICATION_STATUS_UPDATE_TOPIC_ID}" \
    --timeout=60s # Pub/Sub push ack deadline should be shorter than this; processing is backgrounded
    --concurrency=100 # Can handle many concurrent Pub/Sub pushes
    --min-instances=0 \
    --max-instances=3 # Adjust based on expected notification volume
    # Service account for this service will need:
    # - Cloud Datastore User (for Firestore write to notification_log)
    # - Pub/Sub Publisher (to publish to notification-status-updates-topic)
    # - Logs Writer

echo "----------------------------------------------------"
echo "Deployment of ${SERVICE_NAME} initiated."
echo "Service URL will be outputted by gcloud. Note its root down."
echo "Its endpoints like '/notifications/handle/email' will be used for Pub/Sub Push Subscriptions."
echo "The runtime service account for '${SERVICE_NAME}' will need 'Cloud Datastore User' and 'Pub/Sub Publisher' roles."
echo "It will also need to be invokable by Pub/Sub (e.g. 'Cloud Run Invoker' for the Pub/Sub service agent)."
echo "----------------------------------------------------"