#!/usr/bin/env bash
set -e

# --- Configuration ---
export SERVICE_VERSION="0.1.1" # Match your scout_service/app/main.py version
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
export GEMINI_MODEL_NAME_VERTEX="gemini-1.5-flash" # Or your preferred Gemini model
# This URL is for the orchestrator to call the process-user-fixtures endpoint ON ITSELF
# When deployed to Cloud Run, this will be the service's own URL.
# Cloud Run provides a default internal DNS for service-to-service if they are in the same project/region,
# but using the public URL (if secured) or the service URL directly is common.
# For now, we'll set it to be dynamically discovered or assume the service knows its own URL structure for internal calls.
# The gcloud deploy command below will give a URL. We can then update the service if needed,
# or the app can be smart enough if the path is relative.
# A common pattern for self-invocation is to use the K_SERVICE and K_REVISION env vars Cloud Run provides,
# or if the service allows relative paths for internal calls when host isn't specified.
# Let's assume for now the app can call "/scout/process-user-fixtures" on its own host.
# If not, we'd set SCOUT_SERVICE_INTERNAL_URL to its own deployed URL.
# For now, let's NOT set SCOUT_SERVICE_INTERNAL_URL via --set-env-vars in this script,
# and assume the application logic for the orchestrator's httpx calls handles it correctly
# (e.g., by constructing the URL based on the incoming request's host if possible, or a relative path).
# If direct self-URL is needed, we'd typically deploy once, get the URL, then redeploy setting that URL as an env var.
# OR, better, for calls within the same service, do not use HTTP but call the Python function directly.
# Our current orchestrator uses httpx to call its own endpoint. This requires the service to be reachable.

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

# Note on --allow-unauthenticated for Scout Service:
# - /scout/orchestrate-all-user-processing: Will be called by Cloud Scheduler (needs to be invokable, ideally authenticated).
# - /scout/process-user-fixtures: Called by the orchestrator (internal to the service if same instance, or service-to-service).
# For initial deployment and testing the orchestrator via manual trigger, we might keep --allow-unauthenticated.
# Then, secure the orchestrator endpoint for Cloud Scheduler (OIDC) and ensure process-user-fixtures is
# only invokable internally or by trusted sources.
# For now, let's keep --allow-unauthenticated for simplicity in testing the whole chain.
# We'll address securing inter-service calls and scheduler calls more deeply in Step 10/11.

gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_TAG_NAME}" \
    --source=. \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID_VAR}" \
    --set-env-vars="GCP_REGION=${REGION}" \
    --set-env-vars="FIRESTORE_DATABASE_NAME=${FIRESTORE_DATABASE_NAME}" \
    --set-env-vars="LOG_LEVEL=INFO" \
    --set-env-vars="GEMINI_MODEL_NAME_VERTEX=${GEMINI_MODEL_NAME_VERTEX}" \
    # The SCOUT_SERVICE_INTERNAL_URL for the orchestrator's httpx client to call itself:
    # Option 1: Let the app try to determine it or use relative paths if possible (hard for separate process).
    # Option 2: Deploy once, get the URL, then add it here for a second deploy.
    # Option 3 (Best for self-call): The orchestrator logic should ideally call the Python function directly
    #            `await process_fixtures_for_user(user_id)` instead of an HTTP call to itself if running in the same process space.
    #            However, our current orchestrator uses httpx. For it to work, it needs a reachable URL.
    #            Cloud Run service URL will be available after the first deployment.
    #            Let's assume for now, we might need to update this env var after the first deploy if self-HTTP call is strictly needed.
    #            Alternatively, if the service only has ONE instance for the orchestrator, it might not need to call itself over HTTP.
    #            Given our orchestrator uses httpx.AsyncClient, it *will* make an HTTP call.
    #            For now, we'll omit setting SCOUT_SERVICE_INTERNAL_URL and see if relative calls from client work,
    #            or if we need to update it post-deployment.
    # --set-env-vars="SCOUT_SERVICE_INTERNAL_URL=https://your-scout-service-url-from-gcp.a.run.app" \
    --timeout=300s \
    --concurrency=80 # Can handle multiple concurrent /process-user-fixtures calls from orchestrator
    --min-instances=0 \
    --max-instances=3 # Allow some scaling if many users are processed concurrently
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