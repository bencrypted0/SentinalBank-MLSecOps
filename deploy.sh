#!/usr/bin/env bash
# ==============================================================================
# SentinalBank — Docker Deployment Script
# ==============================================================================
# Deploys the full SentinalBank stack locally using Docker Compose:
#   1. MinIO      — S3-compatible object storage for model artifacts
#   2. MLflow     — Experiment tracking and model registry
#   3. Trainer    — One-shot model training (logs model to MLflow/MinIO)
#   4. API App    — FastAPI fraud detection service (loads model from MLflow)
#
# Usage:
#   ./deploy.sh          — Full deploy (clean start)
#   ./deploy.sh --down   — Tear down all containers and volumes
#   ./deploy.sh --logs   — Tail logs from all running services
# ==============================================================================

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log()   { echo -e "${CYAN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
ok()    { echo -e "${GREEN}[  OK]${NC}  $1"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $1"; }

# ── Pre-flight checks ────────────────────────────────────────────────────────
check_dependencies() {
    log "Checking dependencies..."

    if ! command -v docker &>/dev/null; then
        fail "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! docker compose version &>/dev/null; then
        fail "Docker Compose (v2) is not available. Please install Docker Compose."
        exit 1
    fi

    if ! docker info &>/dev/null 2>&1; then
        fail "Docker daemon is not running. Please start Docker."
        exit 1
    fi

    ok "Docker and Docker Compose are available."
}

# ── Teardown ──────────────────────────────────────────────────────────────────
teardown() {
    warn "Tearing down all containers, networks, and volumes..."
    docker compose down -v --remove-orphans 2>/dev/null || true
    ok "All resources removed."
    exit 0
}

# ── Tail logs ─────────────────────────────────────────────────────────────────
tail_logs() {
    log "Tailing logs from all services (Ctrl+C to stop)..."
    docker compose logs -f
    exit 0
}

# ── Parse arguments ──────────────────────────────────────────────────────────
case "${1:-}" in
    --down)   check_dependencies; teardown ;;
    --logs)   tail_logs ;;
    --help|-h)
        echo "Usage: $0 [--down | --logs | --help]"
        echo "  (no args)   Full deploy"
        echo "  --down      Tear down all containers and volumes"
        echo "  --logs      Tail logs from all running services"
        exit 0
        ;;
esac

# ══════════════════════════════════════════════════════════════════════════════
#                           MAIN DEPLOYMENT FLOW
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "============================================================"
echo "  SentinalBank — Docker Deployment"
echo "============================================================"
echo ""

check_dependencies

# ── Step 1: Build images ──────────────────────────────────────────────────────
log "Building Docker images..."
docker compose build --parallel
ok "Images built successfully."

# ── Step 2: Start infrastructure (MinIO + Bucket + MLflow) ────────────────────
log "Starting infrastructure services (MinIO, MLflow)..."
docker compose up -d minio
log "Waiting for MinIO to become healthy..."
docker compose up -d createbucket

# Wait for bucket creation to complete
log "Waiting for bucket initialization..."
docker compose up createbucket 2>/dev/null
ok "MinIO is healthy and 'mlflow' bucket is ready."

# Start MLflow
docker compose up -d mlflow
log "Waiting for MLflow to become healthy..."

# Poll MLflow health (the healthcheck in compose handles retries,
# but we wait here so the script output is clear)
MLFLOW_RETRIES=30
MLFLOW_READY=false
for i in $(seq 1 $MLFLOW_RETRIES); do
    if docker compose exec -T mlflow curl -sf http://localhost:5000/health &>/dev/null; then
        MLFLOW_READY=true
        break
    fi
    sleep 2
done

if [ "$MLFLOW_READY" = true ]; then
    ok "MLflow tracking server is healthy."
else
    fail "MLflow did not become healthy in time. Check logs with: docker compose logs mlflow"
    exit 1
fi

# ── Step 3: Run trainer (one-shot) ────────────────────────────────────────────
echo ""
log "Running model trainer (this will train and log to MLflow/MinIO)..."
echo "------------------------------------------------------------"

# Run trainer in the foreground so we can see output and wait for completion
docker compose run --rm trainer

TRAINER_EXIT=$?
echo "------------------------------------------------------------"

if [ $TRAINER_EXIT -eq 0 ]; then
    ok "Trainer completed successfully. Model is registered in MLflow."
else
    fail "Trainer failed with exit code $TRAINER_EXIT."
    fail "Check trainer logs above. The API app will NOT start."
    exit 1
fi

# ── Step 4: Start the API app ─────────────────────────────────────────────────
echo ""
log "Starting the SentinalBank API app..."
docker compose up -d app

# Wait for the app to respond
APP_RETRIES=20
APP_READY=false
for i in $(seq 1 $APP_RETRIES); do
    if curl -sf http://localhost:8000/health &>/dev/null; then
        APP_READY=true
        break
    fi
    sleep 2
done

if [ "$APP_READY" = true ]; then
    ok "API app is healthy and serving predictions."
else
    warn "API app did not respond on /health within timeout."
    warn "It may still be loading the model. Check logs with: docker compose logs app"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Deployment Complete!"
echo "============================================================"
echo ""
echo -e "  ${CYAN}MinIO Console${NC}   → http://localhost:9001  (minioadmin/minioadmin)"
echo -e "  ${CYAN}MLflow UI${NC}       → http://localhost:5000"
echo -e "  ${CYAN}API (Swagger)${NC}   → http://localhost:8000/docs"
echo -e "  ${CYAN}Health Check${NC}    → http://localhost:8000/health"
echo ""
echo -e "  ${YELLOW}Useful commands:${NC}"
echo "    docker compose logs -f app       # Tail API logs"
echo "    docker compose logs -f mlflow    # Tail MLflow logs"
echo "    ./deploy.sh --down               # Tear down everything"
echo ""
