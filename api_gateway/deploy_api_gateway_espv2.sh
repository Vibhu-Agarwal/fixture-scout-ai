#!/usr/bin/env bash
set -e
set -u
set -o pipefail

# Attempt to source .env if it exists in the current directory
# Useful if you place this script and a specific .env in an api_gateway/ directory
if [ -f .env ]; then
    echo "Sourcing environment variables from $(pwd)/.env"
    source .env
fi

# --- Determine GCP Project ID ---
# Prefer environment variable, then gcloud config, then prompt
if [ -z "${GCP_PROJECT_ID_VAR:-}" ]; then # Use :- to avoid error if var is unset
    GCP_PROJECT_ID_FROM_CONFIG=$(gcloud config get-value project 2>/dev/null)
    if [ -n "${GCP_PROJECT_ID_FROM_CONFIG}" ]; then
        GCP_PROJECT_ID_VAR="${GCP_PROJECT_ID_FROM_CONFIG}"
        echo "Using GCP_PROJECT_ID from gcloud config: ${GCP_PROJECT_ID_VAR}"
    else
        read -r -p "Enter GCP Project ID: " GCP_PROJECT_ID_VAR
    fi
fi
if [ -z "${GCP_PROJECT_ID_VAR}" ]; then
    echo "Error: GCP Project ID is required."
    exit 1
fi
export GCP_PROJECT_ID_VAR # Export it so subsequent commands in script see it if sourced

# --- Determine Region ---
if [ -z "${REGION_VAR:-}" ]; then
    # You might have a default region in gcloud compute/region
    # For now, let's prompt if not set as env var
    read -r -p "Enter GCP Region for ESPv2 Deployment (e.g., asia-south1): " REGION_VAR
fi
if [ -z "${REGION_VAR}" ]; then
    echo "Error: GCP Region is required."
    exit 1
fi
export REGION_VAR

# --- Determine API_GATEWAY_HOST_NAME_START ---
# This is the part of the Endpoints service name before ".endpoints..."
# e.g., if your Endpoints service is "my-api.endpoints.my-proj.cloud.goog", then this is "my-api"
if [ -z "${API_GATEWAY_HOST_NAME_START:-}" ]; then
    read -r -p "Enter the start of your Endpoints Service Name (e.g., fixture-scout-api): " API_GATEWAY_HOST_NAME_START
fi
if [ -z "${API_GATEWAY_HOST_NAME_START}" ]; then
    echo "Error: API Gateway Host Name Start (for Endpoints Service Name) is required."
    exit 1
fi
export API_GATEWAY_HOST_NAME_START


# --- Derived Configuration ---
export ENDPOINTS_SERVICE_NAME="${API_GATEWAY_HOST_NAME_START}.endpoints.${GCP_PROJECT_ID_VAR}.cloud.goog"
export API_GATEWAY_CLOUDRUN_SERVICE_NAME="${API_GATEWAY_HOST_NAME_START}-gateway"

export ESPV2_SA_NAME="espv2-proxy-sa"
export ESPV2_SA_EMAIL="${ESPV2_SA_NAME}@${GCP_PROJECT_ID_VAR}.iam.gserviceaccount.com"

echo "--- Using Configuration ---"
echo "GCP Project ID: ${GCP_PROJECT_ID_VAR}"
echo "Region for ESPv2 Deployment: ${REGION_VAR}"
echo "Cloud Run Service Name for ESPv2: ${API_GATEWAY_CLOUDRUN_SERVICE_NAME}"
echo "Endpoints Service Config Name (target for ESPv2): ${ENDPOINTS_SERVICE_NAME}"
echo "ESPv2 Runtime Service Account: ${ESPV2_SA_EMAIL}"
echo "---------------------------"

echo "Deploying ESPv2 API Gateway (${API_GATEWAY_CLOUDRUN_SERVICE_NAME}) for Endpoints service: ${ENDPOINTS_SERVICE_NAME}"

# Construct ESPv2_ARGS
# The primary way ESPv2 gets its service config is via the --service argument.
# The ENDPOINTS_SERVICE_NAME env var is sometimes a fallback or for other internal ESPv2 mechanisms.
ESPv2_ARGS_STRING="--service=${ENDPOINTS_SERVICE_NAME},--cors_preset=basic"
# If you wanted to pin a specific config ID (version) from `gcloud endpoints services describe ...`
# you would add: ,--version=YOUR_CONFIG_ID
# Example: ESPv2_ARGS_STRING="--service=${ENDPOINTS_SERVICE_NAME},--version=2023-05-18r0,--cors_preset=basic"

# It's generally recommended to pass arguments to ESPv2 via a single ESPv2_ARGS environment variable
# where the arguments themselves are comma-separated (NOT space or ^++^ separated for this env var method).
# The ^++^ separator is for the gcloud --set-env-vars flag itself if you put multiple KEY=VALUE pairs in one --set-env-vars.
# For a single env var value that contains ESPv2 args, commas are the ESPv2 internal delimiter.

gcloud run deploy "${API_GATEWAY_CLOUDRUN_SERVICE_NAME}" \
  --image="gcr.io/endpoints-release/endpoints-runtime-serverless:2" \
  --allow-unauthenticated \
  --platform=managed \
  --project="${GCP_PROJECT_ID_VAR}" \
  --region="${REGION_VAR}" \
  --service-account="${ESPV2_SA_EMAIL}" \
  --set-env-vars="ENDPOINTS_SERVICE_NAME=${ENDPOINTS_SERVICE_NAME}" \
  --set-env-vars="ESPv2_ARGS=${ESPv2_ARGS_STRING}" \
  --port=8080 \
  --cpu=1 \
  --memory=512Mi \
  --min-instances=0 \
  --max-instances=5

echo "----------------------------------------------------"
echo "ESPv2 API Gateway (${API_GATEWAY_CLOUDRUN_SERVICE_NAME}) deployment initiated."
echo "Its URL will be your public API endpoint."
echo "----------------------------------------------------"