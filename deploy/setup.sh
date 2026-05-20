#!/usr/bin/env bash
# =============================================================================
# bitPredict — First-time setup script
# Run ONCE on the VPS as root to bootstrap the deployment.
# Idempotent: safe to re-run.
# =============================================================================
set -euo pipefail

DEPLOY_DIR="/opt/bitpredict"
REPO_URL="https://github.com/leopbar/bitPredict.git"
BRANCH="main"
ENV_FILE="${DEPLOY_DIR}/.env.production"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ── Sanity checks ───────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  echo "Error: must be run as root (try: sudo bash setup.sh)"
  exit 1
fi

log "Checking Docker..."
if ! command -v docker >/dev/null 2>&1; then
  echo "Error: Docker not installed. Install it first."
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Error: Docker Compose v2 not available."
  exit 1
fi

# ── Clone or update repo ────────────────────────────────────────────────────
if [[ -d "${DEPLOY_DIR}/.git" ]]; then
  log "Repo already cloned, pulling latest..."
  cd "${DEPLOY_DIR}"
  git fetch --all
  git reset --hard "origin/${BRANCH}"
else
  log "Cloning repo into ${DEPLOY_DIR}..."
  git clone --branch "${BRANCH}" "${REPO_URL}" "${DEPLOY_DIR}"
  cd "${DEPLOY_DIR}"
fi

# ── Create .env.production from template if absent ──────────────────────────
if [[ ! -f "${ENV_FILE}" ]]; then
  log "Creating ${ENV_FILE} from template (with generated secrets)..."
  cp "${DEPLOY_DIR}/.env.production.example" "${ENV_FILE}"

  PG_PASS=$(openssl rand -hex 24)
  API_KEY=$(openssl rand -hex 32)
  sed -i "s|CHANGE_ME_TO_A_STRONG_PASSWORD|${PG_PASS}|g" "${ENV_FILE}"
  sed -i "s|CHANGE_ME_TO_A_LONG_RANDOM_STRING|${API_KEY}|g" "${ENV_FILE}"

  chmod 600 "${ENV_FILE}"
  log "Generated random POSTGRES_PASSWORD and API_KEY."
else
  log ".env.production already exists, keeping current secrets."
fi

# ── Ensure deploy script is executable ──────────────────────────────────────
chmod +x "${DEPLOY_DIR}/deploy/deploy.sh"

# ── Run first deploy ────────────────────────────────────────────────────────
log "Running first deploy..."
"${DEPLOY_DIR}/deploy/deploy.sh"

log ""
log "========================================================================="
log "Setup complete. bitPredict is running:"
log "  Frontend → http://72.62.96.223:3005"
log "  Backend  → http://72.62.96.223:8004"
log "  Flower   → http://72.62.96.223:5556"
log ""
log "To enable CI/CD from GitHub Actions, add these GitHub secrets:"
log "  SSH_HOST = 72.62.96.223"
log "  SSH_USER = root"
log "  SSH_PRIVATE_KEY = (your deploy key private content)"
log "========================================================================="
