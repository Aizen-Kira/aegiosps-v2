#!/bin/bash

set -e

PROJECT_ID="${GOOGLE_CLOUD_PROJECT}"
REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
BACKEND_SERVICE="aegisops-v2-backend"
FRONTEND_SERVICE="aegisops-v2"

if [ -z "$PROJECT_ID" ]; then
  echo "Error: GOOGLE_CLOUD_PROJECT environment variable not set."
  exit 1
fi

echo "Configuring Docker authentication for Google Container Registry..."
gcloud auth configure-docker

echo "Building backend image..."
docker build -t "gcr.io/${PROJECT_ID}/${BACKEND_SERVICE}" ./backend

echo "Pushing backend image..."
docker push "gcr.io/${PROJECT_ID}/${BACKEND_SERVICE}"

echo "Deploying backend to Cloud Run..."
gcloud run deploy "${BACKEND_SERVICE}" \
  --image "gcr.io/${PROJECT_ID}/${BACKEND_SERVICE}" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY},ARIZE_PHOENIX_API_KEY=${ARIZE_PHOENIX_API_KEY},FIVETRAN_API_KEY=${FIVETRAN_API_KEY},FIVETRAN_API_SECRET=${FIVETRAN_API_SECRET},GITLAB_TOKEN=${GITLAB_TOKEN},GITLAB_PROJECT_ID=${GITLAB_PROJECT_ID},GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --project "${PROJECT_ID}"

BACKEND_URL=$(gcloud run services describe "${BACKEND_SERVICE}" \
  --project "${PROJECT_ID}" \
  --platform managed \
  --region "${REGION}" \
  --format='value(status.url)')

echo "Building frontend image..."
docker build -t "gcr.io/${PROJECT_ID}/${FRONTEND_SERVICE}" ./frontend

echo "Pushing frontend image..."
docker push "gcr.io/${PROJECT_ID}/${FRONTEND_SERVICE}"

echo "Deploying frontend to Cloud Run..."
gcloud run deploy "${FRONTEND_SERVICE}" \
  --image "gcr.io/${PROJECT_ID}/${FRONTEND_SERVICE}" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --set-env-vars "BACKEND_URL=${BACKEND_URL},NEXT_PUBLIC_BACKEND_URL=${BACKEND_URL}" \
  --project "${PROJECT_ID}"

FRONTEND_URL=$(gcloud run services describe "${FRONTEND_SERVICE}" \
  --project "${PROJECT_ID}" \
  --platform managed \
  --region "${REGION}" \
  --format='value(status.url)')

echo "Deployment complete."
echo "Backend URL: ${BACKEND_URL}"
echo "Public app URL: ${FRONTEND_URL}"
