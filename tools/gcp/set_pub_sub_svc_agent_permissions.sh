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

# --- Grant Invoker Roles to Pub/Sub Service Agent ---
# This allows Pub/Sub to make authenticated push requests to your Cloud Run services.
export PROJECT_NUMBER=$(gcloud projects describe "${GCP_PROJECT_ID_VAR}" --format='value(projectNumber)')
if [ -z "$PROJECT_NUMBER" ]; then
    echo "Error: Could not retrieve project number for ${GCP_PROJECT_ID_VAR}"
    exit 1
fi
export PUBSUB_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"

SERVICES_FOR_PUBSUB_PUSH=(
    "notification-service"
    "reminder-service" # For the status update endpoint
)

for SERVICE_NAME_TARGET in "${SERVICES_FOR_PUBSUB_PUSH[@]}"; do
    echo "Granting Cloud Run Invoker role to Pub/Sub Agent ${PUBSUB_SERVICE_AGENT} for service ${SERVICE_NAME_TARGET} in region ${REGION_VAR}"
    gcloud run services add-iam-policy-binding "${SERVICE_NAME_TARGET}" \
        --member="serviceAccount:${PUBSUB_SERVICE_AGENT}" \
        --role="roles/run.invoker" \
        --region="${REGION_VAR}" \
        --project="${GCP_PROJECT_ID_VAR}" \
        --platform=managed
done

export SCHEDULER_SA_EMAIL="${SCHEDULER_SA_NAME}@${GCP_PROJECT_ID_VAR}.iam.gserviceaccount.com"
echo "--- IAM Permissions Setup Complete ---"
echo "Remember to use '${SCHEDULER_SA_EMAIL}' for OIDC authentication in Cloud Scheduler jobs."
echo "Pub/Sub push subscriptions will use '${PUBSUB_SERVICE_AGENT}' for authentication."
echo "After confirming these work, re-deploy the target Cloud Run services without '--allow-unauthenticated'."