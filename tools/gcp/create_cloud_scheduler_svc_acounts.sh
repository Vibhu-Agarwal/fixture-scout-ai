#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration: Define these at the top or ensure they are pre-set in your environment ---
# Option 1: Fetch from current gcloud config (if you are sure it's set correctly there)
# export GCP_PROJECT_ID_VAR=$(gcloud config get-value project)
# export REGION_VAR=$(gcloud config get-value compute/region) # Or a specific region

# Option 2: Hardcode or pass as arguments for this setup script (more explicit for setup)
# For this script, let's prompt if not set, or you can hardcode.
# It's generally better for setup scripts to be explicit or take params.

# Ensure GCP_PROJECT_ID_VAR is set
if [ -z "${GCP_PROJECT_ID_VAR}" ]; then
  read -r -p "Enter GCP Project ID: " GCP_PROJECT_ID_VAR
  if [ -z "${GCP_PROJECT_ID_VAR}" ]; then
    echo "Error: GCP Project ID is required."
    exit 1
  fi
fi

# Ensure REGION_VAR is set (needed for regional resources like Cloud Run services for IAM bindings)
if [ -z "${REGION_VAR}" ]; then
  read -r -p "Enter GCP Region (e.g., asia-south1, us-central1): " REGION_VAR
  if [ -z "${REGION_VAR}" ]; then
    echo "Error: GCP Region is required."
    exit 1
  fi
fi

echo "--- Using Configuration ---"
echo "GCP Project ID: ${GCP_PROJECT_ID_VAR}"
echo "GCP Region: ${REGION_VAR}" # Renamed to avoid conflict if REGION is used later
echo "---------------------------"

# 1. Set the active gcloud project configuration for THIS SCRIPT'S SESSION
echo "Setting active gcloud project to: ${GCP_PROJECT_ID_VAR}"
gcloud config set project "${GCP_PROJECT_ID_VAR}"

# 2. Set the quota project for Application Default Credentials (ADC)
# This aligns the quota project used by client libraries (when running locally with ADC)
# with your active project. It's good practice.
echo "Setting ADC quota project to: ${GCP_PROJECT_ID_VAR}"
gcloud auth application-default set-quota-project "${GCP_PROJECT_ID_VAR}" --quiet # Added --quiet

# --- Create Service Account for Cloud Scheduler ---
export SCHEDULER_SA_NAME="scheduler-invoker-sa"
export SCHEDULER_SA_EMAIL="${SCHEDULER_SA_NAME}@${GCP_PROJECT_ID_VAR}.iam.gserviceaccount.com"

echo "Checking for existing Service Account: ${SCHEDULER_SA_EMAIL}"
if gcloud iam service-accounts describe "${SCHEDULER_SA_EMAIL}" --project="${GCP_PROJECT_ID_VAR}" > /dev/null 2>&1; then
    echo "Service Account ${SCHEDULER_SA_EMAIL} already exists."
else
    echo "Creating Service Account: ${SCHEDULER_SA_EMAIL}"
    gcloud iam service-accounts create "${SCHEDULER_SA_NAME}" \
        --display-name="Service Account for Cloud Scheduler to invoke Cloud Run" \
        --project="${GCP_PROJECT_ID_VAR}"
fi

# --- Grant Invoker Roles to Scheduler Service Account ---
SERVICES_TO_GRANT_SCHEDULER_INVOKER=(
    "football-data-fetcher-service"
    "scout-service"
    "reminder-service" # Only for the scheduler endpoint part
)

for SERVICE_NAME_TARGET in "${SERVICES_TO_GRANT_SCHEDULER_INVOKER[@]}"; do
    echo "Granting Cloud Run Invoker role to ${SCHEDULER_SA_EMAIL} for service ${SERVICE_NAME_TARGET} in region ${REGION_VAR}"
    gcloud run services add-iam-policy-binding "${SERVICE_NAME_TARGET}" \
        --member="serviceAccount:${SCHEDULER_SA_EMAIL}" \
        --role="roles/run.invoker" \
        --region="${REGION_VAR}" \
        --project="${GCP_PROJECT_ID_VAR}" \
        --platform=managed # Important for Cloud Run services
done

