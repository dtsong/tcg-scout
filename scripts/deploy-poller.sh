#!/usr/bin/env bash
# Deploy the tournament polling Cloud Function and Cloud Scheduler job.
#
# Prerequisites:
#   - gcloud CLI authenticated with trainerlab-prod project
#   - Cloud Functions, Cloud Scheduler, and Cloud Build APIs enabled
#   - Service account scout-poller@trainerlab-prod.iam.gserviceaccount.com exists
#     with roles: cloudfunctions.invoker, cloudbuild.builds.editor, storage.objectAdmin
#
# Usage:
#   ./scripts/deploy-poller.sh          # Deploy both function + scheduler
#   ./scripts/deploy-poller.sh function # Deploy function only
#   ./scripts/deploy-poller.sh scheduler # Deploy scheduler only

set -euo pipefail

PROJECT="trainerlab-prod"
REGION="us-central1"
SA="scout-poller@${PROJECT}.iam.gserviceaccount.com"
FUNCTION_NAME="poll-tournaments"
SCHEDULER_NAME="poll-cl-tournaments"

deploy_function() {
  echo "Deploying Cloud Function: ${FUNCTION_NAME}..."
  gcloud functions deploy "${FUNCTION_NAME}" \
    --project "${PROJECT}" \
    --gen2 \
    --runtime python312 \
    --region "${REGION}" \
    --source functions/poll_tournaments/ \
    --entry-point poll_tournaments \
    --trigger-http \
    --no-allow-unauthenticated \
    --memory 128Mi \
    --timeout 30s \
    --service-account "${SA}" \
    --set-env-vars "GCP_PROJECT=${PROJECT},CACHE_BUCKET=tcg-scout-cache,CLOUDBUILD_CONFIG=cloudbuild-scrape.yaml,REPO_OWNER=dtsong,REPO_NAME=tcg-scout,BRANCH=main"
  echo "Cloud Function deployed."
}

deploy_scheduler() {
  local FUNCTION_URL
  FUNCTION_URL="https://${REGION}-${PROJECT}.cloudfunctions.net/${FUNCTION_NAME}"

  echo "Creating Cloud Scheduler job: ${SCHEDULER_NAME}..."
  echo "Schedule: every 2h during JST 10:00-22:00 (UTC 01:00-13:00)"

  # Delete existing job if present (update not supported for all fields)
  gcloud scheduler jobs delete "${SCHEDULER_NAME}" \
    --project "${PROJECT}" \
    --location "${REGION}" \
    --quiet 2>/dev/null || true

  gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
    --project "${PROJECT}" \
    --location "${REGION}" \
    --schedule "0 1,3,5,7,9,11,13 * * *" \
    --time-zone "UTC" \
    --uri "${FUNCTION_URL}" \
    --http-method GET \
    --oidc-service-account-email "${SA}" \
    --description "Poll JP City League API for new tournaments and trigger scrape pipeline"
  echo "Cloud Scheduler job created."
}

case "${1:-all}" in
  function)  deploy_function ;;
  scheduler) deploy_scheduler ;;
  all)       deploy_function && deploy_scheduler ;;
  *)         echo "Usage: $0 [function|scheduler|all]"; exit 1 ;;
esac

echo "Done. Monitor at: https://console.cloud.google.com/functions/details/${REGION}/${FUNCTION_NAME}?project=${PROJECT}"
