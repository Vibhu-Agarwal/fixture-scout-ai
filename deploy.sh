# gcloud functions deploy fixture-scout-register-user \
#     --gen2 \
#     --runtime python312 \
#     --project fixture-scout-ai \
#     --region asia-south1 \
#     --source=. \
#     --entry-point main_app \
#     --trigger-http \
#     --allow-unauthenticated \
#     --set-env-vars GCP_PROJECT=fixture-scout-ai \
#     --set-build-env-vars GOOGLE_FUNCTION_SOURCE=register_user_api/main.py

#     # If using a dedicated service account, add:
#     # --service-account=YOUR_DEDICATED_SERVICE_ACCOUNT_EMAIL

# gcloud functions deploy fixture-scout-register-user \
gcloud builds submit . \
  --config=cloudbuild.yaml \
  --substitutions=_FUNC_DIR="register_user_api",_FUNC_NAME="fixture-scout-register-user",_SERVICE_ACCOUNT=""
