#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# Version of the service. Match this with your application's version if you have one.
export SERVICE_VERSION="0.1.2" # From your football_data_fetcher_service/app/main.py

# Name of the Cloud Run service
export SERVICE_NAME="football-data-fetcher-service"

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

# Firestore Database Name (if not using "(default)")
export FIRESTORE_DATABASE_NAME="fixture-scout-ai-db" # Ensure this is correct for your project

# Data Source Specific Environment Variables
export DATA_SOURCE_TYPE="FOOTBALL_DATA_ORG" # Or "MOCK"
export COMPETITIONS_TO_FETCH="CL,PL,BL1,FL1,SA,PD,WC,EC"
ESCAPED_COMPETITIONS_TO_FETCH="${COMPETITIONS_STRING//,/\\,}"
export DEFAULT_LOOKOUT_WINDOW_DAYS="9"

# !!! IMPORTANT: Football Data API Key !!!
# It's best practice NOT to hardcode secrets in scripts.
# For CI/CD, this would come from a secret manager.
# For manual deployment like this, you can:
# 1. Set it as an environment variable in your shell BEFORE running the script:
#    export FOOTBALL_DATA_API_KEY_VAL="your_actual_api_key"
# 2. Prompt for it (less secure if script is logged):
#    read -sp "Enter FOOTBALL_DATA_API_KEY: " FOOTBALL_DATA_API_KEY_VAL && echo
# For this script, we'll assume it's set as an environment variable FOOTBALL_DATA_API_KEY_VAL
# Ensure FOOTBALL_DATA_API_KEY_VAL is set in your environment before running.
if [ -z "$FOOTBALL_DATA_API_KEY_VAL" ]; then
    echo "Error: FOOTBALL_DATA_API_KEY_VAL environment variable is not set."
    echo "Please set it: export FOOTBALL_DATA_API_KEY_VAL=\"your_api_key\""
    exit 1
fi

# Full Image Tag for Artifact Registry
export IMAGE_TAG_NAME="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID_VAR}/${AR_REPO_NAME}/${SERVICE_NAME}:${SERVICE_VERSION}"

echo "--- Deployment Configuration ---"
echo "Service Name: ${SERVICE_NAME}"
echo "Service Version: ${SERVICE_VERSION}"
echo "GCP Project ID: ${GCP_PROJECT_ID_VAR}"
echo "Region: ${REGION}"
echo "Artifact Registry Repo: ${AR_REPO_NAME}"
echo "Image Tag: ${IMAGE_TAG_NAME}"
echo "Firestore DB Name: ${FIRESTORE_DATABASE_NAME}"
echo "Data Source Type: ${DATA_SOURCE_TYPE}"
echo "Competitions to Fetch: ${COMPETITIONS_TO_FETCH}"
echo "--------------------------------"

# --- Deployment Command ---
echo "Deploying ${SERVICE_NAME} to Cloud Run..."

gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_TAG_NAME}" \
    --source=. \
    --region="${REGION}" \
    --platform=managed \
    --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID_VAR}" \
    --set-env-vars="FIRESTORE_DATABASE_NAME=${FIRESTORE_DATABASE_NAME}" \
    --set-env-vars="LOG_LEVEL=INFO" \
    --set-env-vars="DATA_SOURCE_TYPE=${DATA_SOURCE_TYPE}" \
    --set-env-vars="FOOTBALL_DATA_API_KEY=${FOOTBALL_DATA_API_KEY_VAL}" \
    --set-env-vars="COMPETITIONS_TO_FETCH=${ESCAPED_COMPETITIONS_TO_FETCH}" \
    --set-env-vars="DEFAULT_LOOKOUT_WINDOW_DAYS=${DEFAULT_LOOKOUT_WINDOW_DAYS}" \
    --timeout=300s \
    --concurrency=10 # Data fetchers are usually not highly concurrent for requests, but can take time
    --min-instances=0 \
    --max-instances=1 # Usually, 1 instance is enough for a scheduled data fetcher, adjust if needed
    # --cpu=1 # Default
    # --memory=512Mi # Default, should be enough for this service

echo "--------------------------------"
echo "Deployment of ${SERVICE_NAME} initiated."
echo "Check the Cloud Run console or 'gcloud run services describe ${SERVICE_NAME} --region ${REGION}' for status and URL."
echo "--------------------------------"