#!/usr/bin/env bash
set -e # Exit immediately if a command exits with a non-zero status.

# --- Configuration ---
# Version of the service. Match this with your application's version if you have one.
export SERVICE_VERSION="0.2.0" # From your prompt_optimization_service/app/main.py

# Name of the Cloud Run service
export SERVICE_NAME="prompt-optimization-service"

# GCP Project ID (fetched from current gcloud config)
export GCP_PROJECT_ID_VAR=$(gcloud config get-value project)
if [ -z "$GCP_PROJECT_ID_VAR" ]; then
    echo "GCP_PROJECT_ID is not set. Please set it using 'gcloud config set project YOUR_PROJECT_ID'"
    exit 1
fi

# GCP Region for deployment and Artifact Registry
export REGION="asia-south1" # CHANGE THIS TO YOUR PREFERRED REGION (e.g., us-central1)

# Artifact Registry repository name
export AR_REPO_NAME="fixture-scout-images" # Should be the same for all services

# Firestore Database Name (Not directly used by this service, but good to be consistent if other utils expect it)
# This service primarily uses Vertex AI.
# export FIRESTORE_DATABASE_NAME="fixture-scout-ai-db" # Optional for this service

# Prompt Optimization Service Specific Environment Variables
export OPTIMIZER_GEMINI_MODEL_NAME="gemini-1.5-flash" # Or your preferred Gemini model for optimization

# Full Image Tag for Artifact Registry
export IMAGE_TAG_NAME="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID_VAR}/${AR_REPO_NAME}/${SERVICE_NAME}:${SERVICE_VERSION}"

echo "--- Deployment Configuration for ${SERVICE_NAME} ---"
echo "Service Version: ${SERVICE_VERSION}"
echo "GCP Project ID: ${GCP_PROJECT_ID_VAR}"
echo "Region: ${REGION}"
echo "Image Tag: ${IMAGE_TAG_NAME}"
# echo "Firestore DB Name: ${FIRESTORE_DATABASE_NAME}" # If you decide to pass it
echo "Optimizer Gemini Model: ${OPTIMIZER_GEMINI_MODEL_NAME}"
echo "----------------------------------------------------"

# --- Deployment Command ---
echo "Deploying ${SERVICE_NAME} to Cloud Run..."

gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_TAG_NAME}" \
    --source=. \
    --region="${REGION}" \
    --platform=managed \
    --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID_VAR}" \
    --set-env-vars="GCP_REGION=${REGION}" \
    --set-env-vars="LOG_LEVEL=INFO" \
    --set-env-vars="OPTIMIZER_GEMINI_MODEL_NAME=${OPTIMIZER_GEMINI_MODEL_NAME}" \
    --timeout=120s \
    --concurrency=80 \
    --min-instances=0 \
    --max-instances=2
    # Service account for this service will need:
    # - Vertex AI User (to call Gemini)
    # - Logs Writer

echo "----------------------------------------------------"
echo "Deployment of ${SERVICE_NAME} initiated."
echo "Service URL will be outputted by gcloud. Note it down."
echo "The runtime service account for '${SERVICE_NAME}' will need the 'Vertex AI User' role."
echo "----------------------------------------------------"