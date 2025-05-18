export SERVICE_VERSION="0.2.0"  # Match app version
export SERVICE_NAME="user-management-service"
export GCP_PROJECT_ID_VAR=$(gcloud config get-value project)
export REGION="asia-south1"
export AR_REPO_NAME="fixture-scout-images"
export FIRESTORE_DATABASE_NAME="fixture-scout-ai-db"

export IMAGE_TAG_NAME="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID_VAR}/${AR_REPO_NAME}/${SERVICE_NAME}:${SERVICE_VERSION}"

gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_TAG_NAME}" \
    --source=. \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID_VAR}" \
    --set-env-vars="FIRESTORE_DATABASE_NAME=${FIRESTORE_DATABASE_NAME}" \
    --set-env-vars="LOG_LEVEL=INFO" \
    --timeout=300s \
    --concurrency=80 \
    --min-instances=0 \
    --max-instances=2 # Start with a low max for cost control
    # --service-account=YOUR_SERVICE_ACCOUNT_EMAIL # Optional: if you need a specific SA
    # --vpc-connector=YOUR_VPC_CONNECTOR_NAME # If connecting to VPC resources
    # --cpu=1 # Default is 1
    # --memory=512Mi # Default is 512Mi