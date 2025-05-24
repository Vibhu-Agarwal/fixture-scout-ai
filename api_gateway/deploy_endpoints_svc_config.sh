#!/usr/bin/env bash
set -e
set -u # Important to catch unset variables used in sed

# Source environment-specific variables (URLs, project ID)
# This .env would be in the api_gateway directory and gitignored
if [ -f .env ]; then
    echo "Sourcing environment variables from api_gateway/.env"
    source .env
fi

export GCP_PROJECT_ID_VAR=$(gcloud config get-value project)

# Validate required variables are set (either from .env or shell environment)
: "${GCP_PROJECT_ID_VAR?Error: GCP_PROJECT_ID_VAR is not set. Set it in .env or your shell.}"
: "${USER_MGT_SERVICE_URL_VAL?Error: USER_MGT_SERVICE_URL_VAL is not set.}"
: "${PROMPT_OPT_SERVICE_URL_VAL?Error: PROMPT_OPT_SERVICE_URL_VAL is not set.}"
# Construct the API gateway host name
export API_GATEWAY_HOST_NAME_VAL="${API_GATEWAY_HOST_NAME_START}.endpoints.${GCP_PROJECT_ID_VAR}.cloud.goog"


echo "Generating openapi.yaml from template..."
# Ensure paths are correct relative to where the script is run
sed -e "s|%%USER_MANAGEMENT_SERVICE_URL%%|${USER_MGT_SERVICE_URL_VAL}|g" \
    -e "s|%%PROMPT_OPTIMIZATION_SERVICE_URL%%|${PROMPT_OPT_SERVICE_URL_VAL}|g" \
    -e "s|%%GCP_PROJECT_ID%%|${GCP_PROJECT_ID_VAR}|g" \
    -e "s|%%API_GATEWAY_DNS_NAME%%|${API_GATEWAY_HOST_NAME_VAL}|g" \
    ./openapi.template.yaml > ./openapi.yaml # Output to current dir

echo "Deploying Endpoints service configuration from generated openapi.yaml..."
gcloud endpoints services deploy ./openapi.yaml --project="${GCP_PROJECT_ID_VAR}"
