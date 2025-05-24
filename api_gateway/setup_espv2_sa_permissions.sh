
#!/usr/bin/env bash
set -e
set -u
set -o pipefail

# Source environment-specific variables (URLs, project ID)
# This .env would be in the api_gateway directory and gitignored
if [ -f .env ]; then
    echo "Sourcing environment variables from api_gateway/.env"
    source .env
fi

export GCP_PROJECT_ID_VAR=$(gcloud config get-value project)

# Validate required variables are set (either from .env or shell environment)
: "${GCP_PROJECT_ID_VAR?Error: GCP_PROJECT_ID_VAR is not set. Set it in .env or your shell.}"
: "${REGION_VAR?Error: REGION_VAR is not set. Set it in .env or your shell.}"

# Name for the custom service account for ESPv2
export ESPV2_SA_NAME="espv2-proxy-sa" # You can customize this name
export ESPV2_SA_EMAIL="${ESPV2_SA_NAME}@${GCP_PROJECT_ID_VAR}.iam.gserviceaccount.com"

echo "--- Using Configuration ---"
echo "GCP Project ID: ${GCP_PROJECT_ID_VAR}"
echo "Region for backend services: ${REGION_VAR}"
echo "ESPv2 Service Account Name: ${ESPV2_SA_NAME}"
echo "ESPv2 Service Account Email: ${ESPV2_SA_EMAIL}"
echo "---------------------------"

# 1. Create the ESPv2 Service Account (if it doesn't exist)
echo "Checking for existing Service Account: ${ESPV2_SA_EMAIL}"
if gcloud iam service-accounts describe "${ESPV2_SA_EMAIL}" --project="${GCP_PROJECT_ID_VAR}" > /dev/null 2>&1; then
    echo "Service Account ${ESPV2_SA_EMAIL} already exists."
else
    echo "Creating Service Account: ${ESPV2_SA_EMAIL}"
    gcloud iam service-accounts create "${ESPV2_SA_NAME}" \
        --display-name="Service Account for ESPv2 API Gateway Proxy" \
        --project="${GCP_PROJECT_ID_VAR}"
fi

# 2. Grant ESPv2 SA permissions to invoke backend services
BACKEND_SERVICES=(
    "user-management-service"
    "prompt-optimization-service"
)

for SERVICE_NAME_TARGET in "${BACKEND_SERVICES[@]}"; do
    echo "Granting Cloud Run Invoker role to ${ESPV2_SA_EMAIL} for backend service ${SERVICE_NAME_TARGET}"
    gcloud run services add-iam-policy-binding "${SERVICE_NAME_TARGET}" \
        --member="serviceAccount:${ESPV2_SA_EMAIL}" \
        --role="roles/run.invoker" \
        --region="${REGION_VAR}" \
        --project="${GCP_PROJECT_ID_VAR}" \
        --platform=managed
done

# 3. Grant ESPv2 SA permissions needed for Endpoints integration
echo "Granting Service Controller User/Agent role to ${ESPV2_SA_EMAIL} on project ${GCP_PROJECT_ID_VAR}"
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID_VAR}" \
    --member="serviceAccount:${ESPV2_SA_EMAIL}" \
    --role="roles/endpoints.serviceAgent" # Allows ESPv2 to report to Service Control

echo "Granting Cloud Trace Agent role to ${ESPV2_SA_EMAIL} on project ${GCP_PROJECT_ID_VAR} (for tracing)"
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID_VAR}" \
    --member="serviceAccount:${ESPV2_SA_EMAIL}" \
    --role="roles/cloudtrace.agent"

echo "--- ESPv2 Service Account Permissions Setup Complete ---"
echo "Service Account ${ESPV2_SA_EMAIL} is now configured."