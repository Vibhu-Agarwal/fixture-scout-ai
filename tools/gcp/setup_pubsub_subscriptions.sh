#!/usr/bin/env bash
set -e # Exit immediately if a command exits with a non-zero status.
set -u # Treat unset variables as an error when substituting.
set -o pipefail # Causes a pipeline to return the exit status of the last command in the pipe that returned a non-zero return value.

# --- Function to display usage ---
usage() {
    echo "Usage: $0 -p <gcp_project_id> -r <gcp_region> -u <your_user_email> -n <notification_service_url> -m <reminder_service_url>"
    echo "  -p GCP_PROJECT_ID: Your Google Cloud Project ID."
    echo "  -r GCP_REGION: The GCP region where your Cloud Run services are deployed (e.g., asia-south1)."
    echo "  -u YOUR_USER_EMAIL: Your Google account email (e.g., myEmail@gmail.com)."
    echo "  -n NOTIFICATION_SERVICE_URL: The full HTTPS URL of your deployed Notification Service."
    echo "  -m REMINDER_SERVICE_URL: The full HTTPS URL of your deployed Reminder Service."
    exit 1
}

# --- Parse Command-Line Flags ---
GCP_PROJECT_ID_VAR=""
REGION_VAR=""
YOUR_USER_EMAIL=""
NOTIFICATION_SERVICE_URL=""
REMINDER_SERVICE_URL=""

while getopts ":p:r:u:n:m:" opt; do
  case ${opt} in
    p ) GCP_PROJECT_ID_VAR=$OPTARG ;;
    r ) REGION_VAR=$OPTARG ;;
    u ) YOUR_USER_EMAIL=$OPTARG ;;
    n ) NOTIFICATION_SERVICE_URL=$OPTARG ;;
    m ) REMINDER_SERVICE_URL=$OPTARG ;;
    \? ) echo "Invalid Option: -$OPTARG" 1>&2; usage ;;
    : ) echo "Invalid Option: -$OPTARG requires an argument" 1>&2; usage ;;
  esac
done
shift $((OPTIND -1))

# --- Validate required inputs ---
if [ -z "${GCP_PROJECT_ID_VAR}" ] || [ -z "${REGION_VAR}" ] || [ -z "${YOUR_USER_EMAIL}" ] || [ -z "${NOTIFICATION_SERVICE_URL}" ] || [ -z "${REMINDER_SERVICE_URL}" ]; then
    echo "Error: Missing required arguments."
    usage
fi

echo "--- Using Configuration ---"
echo "GCP Project ID: ${GCP_PROJECT_ID_VAR}"
echo "GCP Region: ${REGION_VAR}"
echo "User Email: ${YOUR_USER_EMAIL}"
echo "Notification Service URL: ${NOTIFICATION_SERVICE_URL}"
echo "Reminder Service URL: ${REMINDER_SERVICE_URL}"
echo "---------------------------"

# --- Set Active Project for gcloud ---
echo "Setting active gcloud project to: ${GCP_PROJECT_ID_VAR}"
gcloud config set project "${GCP_PROJECT_ID_VAR}"

# --- Define Custom Service Account for Pub/Sub Push ---
export CUSTOM_PUSHER_SA_NAME="fixture-scout-pubsub-pusher" # You can change this name if desired
export CUSTOM_PUSHER_SA_EMAIL="${CUSTOM_PUSHER_SA_NAME}@${GCP_PROJECT_ID_VAR}.iam.gserviceaccount.com"

# 1. Create the Custom Service Account (if it doesn't exist)
echo "Checking/Creating Custom Service Account for Pub/Sub push: ${CUSTOM_PUSHER_SA_EMAIL}"
if ! gcloud iam service-accounts describe "${CUSTOM_PUSHER_SA_EMAIL}" --project="${GCP_PROJECT_ID_VAR}" > /dev/null 2>&1; then
    gcloud iam service-accounts create "${CUSTOM_PUSHER_SA_NAME}" \
        --display-name="Fixture Scout PubSub Push Authenticator" \
        --description="Service account used by Pub/Sub to make authenticated push requests to Cloud Run services." \
        --project="${GCP_PROJECT_ID_VAR}"
    echo "Service Account ${CUSTOM_PUSHER_SA_EMAIL} created."
else
    echo "Service Account ${CUSTOM_PUSHER_SA_EMAIL} already exists."
fi

# 2. Grant YOUR USER ACCOUNT the "Service Account User" role ON THE CUSTOM SA
# This allows your user to configure Pub/Sub subscriptions to use (actAs) this custom SA.
echo "Granting 'Service Account User' role to ${YOUR_USER_EMAIL} on SA ${CUSTOM_PUSHER_SA_EMAIL}..."
gcloud iam service-accounts add-iam-policy-binding "${CUSTOM_PUSHER_SA_EMAIL}" \
    --member="user:${YOUR_USER_EMAIL}" \
    --role="roles/iam.serviceAccountUser" \
    --project="${GCP_PROJECT_ID_VAR}" \
    || echo "Warning: Failed to grant 'Service Account User' role. It might already exist or there's another permission issue."


# 3. Grant THE CUSTOM SA the "Cloud Run Invoker" role ON THE TARGET CLOUD RUN SERVICES
# This allows the custom SA (when impersonated by Pub/Sub) to invoke the push endpoints.
echo "Granting 'Cloud Run Invoker' role to ${CUSTOM_PUSHER_SA_EMAIL} for Notification Service..."
gcloud run services add-iam-policy-binding notification-service \
    --member="serviceAccount:${CUSTOM_PUSHER_SA_EMAIL}" \
    --role="roles/run.invoker" \
    --region="${REGION_VAR}" \
    --platform=managed \
    --project="${GCP_PROJECT_ID_VAR}" \
    || echo "Warning: Failed to grant 'Cloud Run Invoker' to Notification Service. Check service existence/permissions."

echo "Granting 'Cloud Run Invoker' role to ${CUSTOM_PUSHER_SA_EMAIL} for Reminder Service (status update endpoint)..."
gcloud run services add-iam-policy-binding reminder-service \
    --member="serviceAccount:${CUSTOM_PUSHER_SA_EMAIL}" \
    --role="roles/run.invoker" \
    --region="${REGION_VAR}" \
    --platform=managed \
    --project="${GCP_PROJECT_ID_VAR}" \
    || echo "Warning: Failed to grant 'Cloud Run Invoker' to Reminder Service. Check service existence/permissions."


# --- Topic IDs (should match service configurations) ---
EMAIL_TOPIC_ID="email-notifications-topic"
PHONE_MOCK_TOPIC_ID="mock-phone-call-notifications-topic"
STATUS_UPDATE_TOPIC_ID="notification-status-updates-topic"

# --- Create Pub/Sub Push Subscriptions using the CUSTOM Service Account ---

# Subscription 1: For Notification Service (Email)
EMAIL_SUBSCRIPTION_ID="email-notifications-sub-push"
echo "Creating/Updating Pub/Sub Subscription: ${EMAIL_SUBSCRIPTION_ID} for topic ${EMAIL_TOPIC_ID}..."
gcloud pubsub subscriptions create "${EMAIL_SUBSCRIPTION_ID}" \
    --topic="${EMAIL_TOPIC_ID}" \
    --topic-project="${GCP_PROJECT_ID_VAR}" \
    --push-endpoint="${NOTIFICATION_SERVICE_URL}/notifications/handle/email" \
    --ack-deadline=60 \
    --push-auth-service-account="${CUSTOM_PUSHER_SA_EMAIL}" \
    --push-auth-token-audience="${NOTIFICATION_SERVICE_URL}" \
    --project="${GCP_PROJECT_ID_VAR}" \
    || echo "Subscription ${EMAIL_SUBSCRIPTION_ID} might already exist or failed. Check previous errors/permissions."

# Subscription 2: For Notification Service (Mock Phone Call)
PHONE_MOCK_SUBSCRIPTION_ID="phone-mock-notifications-sub-push"
echo "Creating/Updating Pub/Sub Subscription: ${PHONE_MOCK_SUBSCRIPTION_ID} for topic ${PHONE_MOCK_TOPIC_ID}..."
gcloud pubsub subscriptions create "${PHONE_MOCK_SUBSCRIPTION_ID}" \
    --topic="${PHONE_MOCK_TOPIC_ID}" \
    --topic-project="${GCP_PROJECT_ID_VAR}" \
    --push-endpoint="${NOTIFICATION_SERVICE_URL}/notifications/handle/phone-mock" \
    --ack-deadline=60 \
    --push-auth-service-account="${CUSTOM_PUSHER_SA_EMAIL}" \
    --push-auth-token-audience="${NOTIFICATION_SERVICE_URL}" \
    --project="${GCP_PROJECT_ID_VAR}" \
    || echo "Subscription ${PHONE_MOCK_SUBSCRIPTION_ID} might already exist or failed. Check previous errors/permissions."

# Subscription 3: For Reminder Service (Status Updates)
STATUS_UPDATE_SUBSCRIPTION_ID="reminder-status-update-sub-push"
echo "Creating/Updating Pub/Sub Subscription: ${STATUS_UPDATE_SUBSCRIPTION_ID} for topic ${STATUS_UPDATE_TOPIC_ID}..."
gcloud pubsub subscriptions create "${STATUS_UPDATE_SUBSCRIPTION_ID}" \
    --topic="${STATUS_UPDATE_TOPIC_ID}" \
    --topic-project="${GCP_PROJECT_ID_VAR}" \
    --push-endpoint="${REMINDER_SERVICE_URL}/reminders/handle-status-update" \
    --ack-deadline=60 \
    --push-auth-service-account="${CUSTOM_PUSHER_SA_EMAIL}" \
    --push-auth-token-audience="${REMINDER_SERVICE_URL}" \
    --project="${GCP_PROJECT_ID_VAR}" \
    || echo "Subscription ${STATUS_UPDATE_SUBSCRIPTION_ID} might already exist or failed. Check previous errors/permissions."

echo "--- Pub/Sub Auth and Subscription Setup Attempted ---"
echo "Verify the custom service account (${CUSTOM_PUSHER_SA_EMAIL}) and its IAM bindings."
echo "Verify the Pub/Sub subscriptions in the GCP Console."
echo "Ensure the topics (${EMAIL_TOPIC_ID}, ${PHONE_MOCK_TOPIC_ID}, ${STATUS_UPDATE_TOPIC_ID}) exist or are created by your services on startup."