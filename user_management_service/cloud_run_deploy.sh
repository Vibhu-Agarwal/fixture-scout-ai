#!/usr/bin/env bash
set -e

# --- Configuration ---
export SERVICE_VERSION="0.4.0"
export SERVICE_NAME="user-management-service"
export GCP_PROJECT_ID_VAR=$(gcloud config get-value project)
if [ -z "$GCP_PROJECT_ID_VAR" ]; then
    echo "GCP_PROJECT_ID is not set. Please set it using 'gcloud config set project YOUR_PROJECT_ID'"
    exit 1
fi
export REGION="asia-south1"
export AR_REPO_NAME="fixture-scout-images"
export FIRESTORE_DATABASE_NAME="fixture-scout-ai-db"

# Names of the secrets in Google Cloud Secret Manager
export JWT_SECRET_NAME="FIXTURE_SCOUT_AI_JWT_SECRET"
export GOOGLE_CLIENT_ID_SECRET_NAME="FIXTURE_SCOUT_AI_OAUTH_CLIENT_ID"

export IMAGE_TAG_NAME="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID_VAR}/${AR_REPO_NAME}/${SERVICE_NAME}:${SERVICE_VERSION}"

echo "--- Deployment Configuration for ${SERVICE_NAME} ---"
echo "Service Version: ${SERVICE_VERSION}"
echo "GCP Project ID: ${GCP_PROJECT_ID_VAR}"
echo "Region: ${REGION}"
echo "Image Tag: ${IMAGE_TAG_NAME}"
echo "Firestore DB Name: ${FIRESTORE_DATABASE_NAME}"
echo "JWT Secret Name: ${JWT_SECRET_NAME}"
echo "Google Client ID Secret Name: ${GOOGLE_CLIENT_ID_SECRET_NAME}"
echo "----------------------------------------------------"

echo "Deploying ${SERVICE_NAME} to Cloud Run..."

gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_TAG_NAME}" \
    --source=. \
    --region="${REGION}" \
    --platform=managed \
    --update-secrets=JWT_SECRET_KEY="${JWT_SECRET_NAME}:latest" \
    --update-secrets=GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID_SECRET_NAME}:latest" \
    --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID_VAR}" \
    --set-env-vars="FIRESTORE_DATABASE_NAME=${FIRESTORE_DATABASE_NAME}" \
    --set-env-vars="LOG_LEVEL=INFO" \
    --set-env-vars="JWT_ALGORITHM=HS256" \
    --set-env-vars="JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60" \
    --timeout=300s \
    --concurrency=80 \
    --min-instances=0 \
    --max-instances=2

    # Service account for this service will need:
    # - Cloud Datastore User (for Firestore)
    # - Secret Manager Secret Accessor (for the specified secrets)
    # - Logs Writer

echo "----------------------------------------------------"
echo "Deployment of ${SERVICE_NAME} initiated."
echo "Service URL will be outputted by gcloud. Note it down."
echo "Ensure the runtime service account for '${SERVICE_NAME}' has 'Secret Manager Secret Accessor' role for '${JWT_SECRET_NAME}' and '${GOOGLE_CLIENT_ID_SECRET_NAME}'."
echo "It also needs 'Cloud Datastore User' role."
echo "----------------------------------------------------"