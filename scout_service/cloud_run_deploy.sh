#!/usr/bin/env bash
set -e

# --- Configuration ---
export SERVICE_VERSION="0.2.0" # Match your scout_service/app/main.py version
export SERVICE_NAME="scout-service"
export GCP_PROJECT_ID_VAR=$(gcloud config get-value project)
if [ -z "$GCP_PROJECT_ID_VAR" ]; then
    echo "GCP_PROJECT_ID is not set. Please set it using 'gcloud config set project YOUR_PROJECT_ID'"
    exit 1
fi
export REGION="asia-south1" # CHANGE THIS TO YOUR PREFERRED REGION
export AR_REPO_NAME="fixture-scout-images"
export FIRESTORE_DATABASE_NAME="fixture-scout-ai-db" # Ensure this is correct

# Scout Service Specific Environment Variables
export GEMINI_MODEL_NAME_VERTEX="gemini-2.5-flash-lite"

export IMAGE_TAG_NAME="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID_VAR}/${AR_REPO_NAME}/${SERVICE_NAME}:${SERVICE_VERSION}"

echo "--- Deployment Configuration for ${SERVICE_NAME} ---"
echo "Service Version: ${SERVICE_VERSION}"
echo "GCP Project ID: ${GCP_PROJECT_ID_VAR}"
echo "Region: ${REGION}"
echo "Image Tag: ${IMAGE_TAG_NAME}"
echo "Firestore DB Name: ${FIRESTORE_DATABASE_NAME}"
echo "Gemini Model: ${GEMINI_MODEL_NAME_VERTEX}"
echo "----------------------------------------------------"

echo "Deploying ${SERVICE_NAME} to Cloud Run..."

gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_TAG_NAME}" \
    --source=. \
    --region="${REGION}" \
    --platform=managed \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=${GCP_PROJECT_ID_VAR}" \
    --set-env-vars="FIRESTORE_DATABASE_NAME=${FIRESTORE_DATABASE_NAME}" \
    --set-env-vars="LOG_LEVEL=INFO" \
    --set-env-vars="LLM_MAX_OUTPUT_TOKENS=8192" \
    --set-env-vars="LLM_TEMPERATURE=0.3" \
    --set-env-vars="GEMINI_MODEL_NAME_VERTEX=${GEMINI_MODEL_NAME_VERTEX}" \
    --timeout=300s \
    --concurrency=80 \
    --min-instances=0 \
    --max-instances=3

    # Service account for this service will need:
    # - Cloud Datastore User (for Firestore)
    # - Vertex AI User (to call Gemini)
    # - Logs Writer
    # --cpu=1 # Consider increasing if LLM processing is CPU intensive, but start with 1
    # --memory=512Mi # Or 1Gi if needed for LLM client libraries or concurrent processing

echo "----------------------------------------------------"
echo "Deployment of ${SERVICE_NAME} initiated."
echo "Service URL will be outputted by gcloud. Note it down."
echo "The runtime service account for '${SERVICE_NAME}' will need 'Vertex AI User' and 'Cloud Datastore User' roles."
echo "----------------------------------------------------"