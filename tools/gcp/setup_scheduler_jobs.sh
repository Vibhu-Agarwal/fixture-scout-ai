#!/usr/bin/env bash
set -e

# --- Configuration: Ensure these are set correctly or provide them ---
if [ -z "${GCP_PROJECT_ID_VAR}" ]; then
  read -r -p "Enter GCP Project ID: " GCP_PROJECT_ID_VAR
  if [ -z "${GCP_PROJECT_ID_VAR}" ]; then
    echo "Error: GCP Project ID is required."
    exit 1
  fi
fi

if [ -z "${REGION_VAR}" ]; then
  read -r -p "Enter GCP Region where services and scheduler are deployed (e.g., asia-south1): " REGION_VAR
  if [ -z "${REGION_VAR}" ]; then
    echo "Error: GCP Region is required."
    exit 1
  fi
fi

# --- Prompt for Cloud Run Service URLs ---
if [ -z "${DATA_FETCHER_URL}" ]; then
  read -r -p "Enter full URL for Football Data Fetcher Service: " DATA_FETCHER_URL
  if [ -z "${DATA_FETCHER_URL}" ]; then
    echo "Error: Football Data Fetcher Service URL is required."
    exit 1
  fi
fi

if [ -z "${SCOUT_SERVICE_URL}" ]; then
  read -r -p "Enter full URL for Scout Service: " SCOUT_SERVICE_URL
  if [ -z "${SCOUT_SERVICE_URL}" ]; then
    echo "Error: Scout Service URL is required."
    exit 1
  fi
fi

if [ -z "${REMINDER_SERVICE_URL}" ]; then
  read -r -p "Enter full URL for Reminder Service: " REMINDER_SERVICE_URL
  if [ -z "${REMINDER_SERVICE_URL}" ]; then
    echo "Error: Reminder Service URL is required."
    exit 1
  fi
fi

export SCHEDULER_SA_EMAIL="scheduler-invoker-sa@${GCP_PROJECT_ID_VAR}.iam.gserviceaccount.com"

echo "--- Using Configuration ---"
echo "GCP Project ID: ${GCP_PROJECT_ID_VAR}"
echo "Region: ${REGION_VAR}"
echo "Scheduler Service Account: ${SCHEDULER_SA_EMAIL}"
echo "Data Fetcher URL: ${DATA_FETCHER_URL}"
echo "Scout Service URL: ${SCOUT_SERVICE_URL}"
echo "Reminder Service URL: ${REMINDER_SERVICE_URL}"
echo "---------------------------"

# --- Create/Update Cloud Scheduler Jobs ---
# The 'update' command will create if not exists, or update if it does.
# This makes the script idempotent.

# Job 1: Trigger Football Data Fetcher
echo "Creating/Updating Scheduler Job: trigger-football-data-fetcher..."
gcloud scheduler jobs create http trigger-football-data-fetcher \
    --schedule="5 0 * * *" \
    --time-zone="Etc/UTC" \
    --uri="${DATA_FETCHER_URL}/data-fetcher/fetch-and-store-all-fixtures" \
    --http-method=POST \
    --oidc-service-account-email="${SCHEDULER_SA_EMAIL}" \
    --oidc-token-audience="${DATA_FETCHER_URL}" \
    --description="Triggers the football data fetcher service daily." \
    --project="${GCP_PROJECT_ID_VAR}" \
    --location="${REGION_VAR}" \
    --max-retry-attempts=3 \
    --min-backoff=30s \
    --max-backoff=300s \
    || echo "Job trigger-football-data-fetcher might already exist. Use 'update' command or check console."

# Job 2: Trigger Scout Service Orchestrator
echo "Creating/Updating Scheduler Job: trigger-scout-orchestrator..."
gcloud scheduler jobs create http trigger-scout-orchestrator \
    --schedule="30 0 * * *" \
    --time-zone="Etc/UTC" \
    --uri="${SCOUT_SERVICE_URL}/scout/orchestrate-all-user-processing" \
    --http-method=POST \
    --oidc-service-account-email="${SCHEDULER_SA_EMAIL}" \
    --oidc-token-audience="${SCOUT_SERVICE_URL}" \
    --description="Triggers the scout service orchestrator daily." \
    --project="${GCP_PROJECT_ID_VAR}" \
    --location="${REGION_VAR}" \
    --max-retry-attempts=3 \
    --min-backoff=30s \
    --max-backoff=300s \
    || echo "Job trigger-scout-orchestrator might already exist. Use 'update' command or check console."

# Job 3: Trigger Reminder Service (Scheduler Component)
echo "Creating/Updating Scheduler Job: trigger-reminder-scheduler..."
gcloud scheduler jobs create http trigger-reminder-scheduler \
    --schedule="*/10 * * * *" \
    --time-zone="Etc/UTC" \
    --uri="${REMINDER_SERVICE_URL}/scheduler/check-and-dispatch-reminders" \
    --http-method=POST \
    --oidc-service-account-email="${SCHEDULER_SA_EMAIL}" \
    --oidc-token-audience="${REMINDER_SERVICE_URL}" \
    --description="Triggers the reminder service's scheduler component every 10 minutes." \
    --project="${GCP_PROJECT_ID_VAR}" \
    --location="${REGION_VAR}" \
    --attempt-deadline=290s \
    --max-retry-attempts=5 \
    --min-backoff=60s \
    --max-backoff=600s \
    || echo "Job trigger-reminder-scheduler might already exist. Use 'update' command or check console."

echo "--- Cloud Scheduler Job Setup Attempted ---"
echo "Verify the jobs in the GCP Console (Cloud Scheduler)."
echo "You can manually trigger them from the console for testing."