#!/usr/bin/env bash
# =============================================================================
# bitPredict — Production deploy script
# Runs on the VPS via GitHub Actions SSH on every push to main.
# =============================================================================
set -euo pipefail

DEPLOY_DIR="/opt/bitpredict"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"
LOG_FILE="/var/log/bitpredict-deploy.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

cd "${DEPLOY_DIR}"

COMPOSE="docker compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE}"

log "====== Deploy started ======"

# ── Pull latest code ────────────────────────────────────────────────────────
log "Fetching latest code from GitHub..."
git fetch --all
git reset --hard origin/main

# ── Build new images ────────────────────────────────────────────────────────
log "Building Docker images..."
$COMPOSE build

# ── Restart services ────────────────────────────────────────────────────────
log "Recreating containers..."
$COMPOSE up -d --remove-orphans

# ── Run migrations ──────────────────────────────────────────────────────────
log "Applying Alembic migrations..."
$COMPOSE exec -T backend alembic upgrade head || {
  log "WARNING: alembic upgrade failed (may be a first run, will retry after backend is healthy)"
  sleep 10
  $COMPOSE exec -T backend alembic upgrade head
}

# ── Health check ────────────────────────────────────────────────────────────
log "Waiting for backend health check..."
MAX_WAIT=120
WAITED=0
until curl -sf http://localhost:8004/health > /dev/null 2>&1 || [ "$WAITED" -ge "$MAX_WAIT" ]; do
  sleep 5
  WAITED=$((WAITED + 5))
done

if curl -sf http://localhost:8004/health > /dev/null 2>&1; then
  log "Backend healthy ✓"
else
  log "ERROR: backend failed health check after ${MAX_WAIT}s"
  $COMPOSE logs --tail=50 backend
  exit 1
fi

# ── Cleanup dangling images ─────────────────────────────────────────────────
log "Pruning dangling images..."
docker image prune -f >> "$LOG_FILE" 2>&1 || true

log "====== Deploy successful ======"
