#!/usr/bin/env bash
# =============================================================================
# bitPredict — First-time setup script for the NEW VPS (13.140.166.97)
# Run ONCE as root to bootstrap the deployment.
# Idempotent: safe to re-run.
#
# Prerequisites:
#   - Ubuntu 22.04+ on the VPS
#   - DNS: bitpredict.lbai.dev → 13.140.166.97 already propagated
#
# Usage:
#   sudo bash setup.sh
# =============================================================================
set -euo pipefail

DOMAIN="bitpredict.lbai.dev"
DEPLOY_DIR="/opt/bitpredict"
REPO_URL="https://github.com/leopbar/bitPredict.git"
BRANCH="main"
ENV_FILE="${DEPLOY_DIR}/.env.production"
NGINX_CONF_SRC="${DEPLOY_DIR}/deploy/nginx.conf"
NGINX_SITE="/etc/nginx/sites-available/bitpredict"
ADMIN_EMAIL="lbarretti@gmail.com"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ── Sanity checks ─────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  echo "Error: must be run as root (try: sudo bash setup.sh)"
  exit 1
fi

# ── Install Docker ─────────────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker..."
  apt-get update -qq
  apt-get install -y --no-install-recommends ca-certificates curl gnupg lsb-release
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
  log "Docker installed."
else
  log "Docker already installed."
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Error: Docker Compose v2 plugin not available after install."
  exit 1
fi

# ── Install Nginx + Certbot ────────────────────────────────────────────────────
if ! command -v nginx >/dev/null 2>&1; then
  log "Installing Nginx..."
  apt-get update -qq
  apt-get install -y nginx
  systemctl enable nginx
  log "Nginx installed."
fi

if ! command -v certbot >/dev/null 2>&1; then
  log "Installing Certbot..."
  apt-get install -y certbot python3-certbot-nginx
  log "Certbot installed."
fi

# ── Clone or update repo ───────────────────────────────────────────────────────
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

chmod +x "${DEPLOY_DIR}/deploy/deploy.sh"

# ── Write .env.production ──────────────────────────────────────────────────────
if [[ -n "${VPS_ENV:-}" ]]; then
  log "Writing .env.production from VPS_ENV env var..."
  printf '%s' "$VPS_ENV" > "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
elif [[ ! -f "${ENV_FILE}" ]]; then
  log "Creating ${ENV_FILE} from template (with generated secrets)..."
  cp "${DEPLOY_DIR}/.env.production.example" "${ENV_FILE}"

  PG_PASS=$(openssl rand -hex 24)
  API_KEY=$(openssl rand -hex 32)
  FLOWER_PASS=$(openssl rand -hex 16)
  sed -i "s|CHANGE_ME_TO_A_STRONG_PASSWORD|${PG_PASS}|g" "${ENV_FILE}"
  sed -i "s|CHANGE_ME_TO_A_LONG_RANDOM_STRING|${API_KEY}|g" "${ENV_FILE}"
  sed -i "s|admin:CHANGE_ME_TO_A_STRONG_PASSWORD|admin:${FLOWER_PASS}|g" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
  log "Generated random POSTGRES_PASSWORD, API_KEY, FLOWER_BASIC_AUTH."
  log "IMPORTANT: Save these from ${ENV_FILE} and store them in GitHub secret VPS_ENV."
else
  log ".env.production already exists, keeping current secrets."
fi

# ── Configure Nginx site (HTTP only for now — Certbot adds HTTPS) ──────────────
if [[ ! -f "${NGINX_SITE}" ]]; then
  log "Writing Nginx site config (HTTP only for Certbot challenge)..."
  cat > "${NGINX_SITE}" <<'NGINX'
server {
    listen 80;
    server_name bitpredict.lbai.dev;

    location / {
        proxy_pass         http://127.0.0.1:3005;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   Upgrade           $http_upgrade;
        proxy_set_header   Connection        'upgrade';
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        client_max_body_size 10M;
    }
}
NGINX
  ln -sf "${NGINX_SITE}" /etc/nginx/sites-enabled/bitpredict
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl reload nginx
  log "Nginx HTTP site active."
fi

# ── Run first Docker deploy ────────────────────────────────────────────────────
log "Running first deploy (this builds Docker images — may take 10-15 min)..."
"${DEPLOY_DIR}/deploy/deploy.sh"

# ── Obtain SSL certificate ─────────────────────────────────────────────────────
log "Waiting for DNS to resolve ${DOMAIN} → 13.140.166.97..."
MAX_DNS_WAIT=300
DNS_WAITED=0
until [[ "$(dig +short "${DOMAIN}" | tail -1)" == "13.140.166.97" ]] || [[ "$DNS_WAITED" -ge "$MAX_DNS_WAIT" ]]; do
  sleep 10
  DNS_WAITED=$((DNS_WAITED + 10))
  log "  DNS not yet propagated (${DNS_WAITED}s)..."
done

RESOLVED_IP=$(dig +short "${DOMAIN}" | tail -1)
if [[ "$RESOLVED_IP" != "13.140.166.97" ]]; then
  log "WARNING: DNS still not resolving to 13.140.166.97 (got: ${RESOLVED_IP:-none})."
  log "Skipping Certbot for now. Re-run once DNS propagates:"
  log "  certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos -m ${ADMIN_EMAIL}"
else
  if [[ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
    log "Obtaining Let's Encrypt certificate for ${DOMAIN}..."
    certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${ADMIN_EMAIL}"
    log "Certificate obtained. Nginx updated with HTTPS config."

    # Install the final HTTPS-aware nginx.conf from the repo
    cp "${NGINX_CONF_SRC}" "${NGINX_SITE}"
    nginx -t && systemctl reload nginx
    log "HTTPS Nginx config applied."
  else
    log "Certificate already exists, skipping Certbot."
  fi

  # Ensure auto-renewal cron is active
  if ! crontab -l 2>/dev/null | grep -q certbot; then
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --deploy-hook 'systemctl reload nginx'") | crontab -
    log "Certbot auto-renewal cron installed."
  fi
fi

log ""
log "========================================================================="
log "Setup complete. bitPredict is running:"
log "  Frontend → https://${DOMAIN}"
log "  Backend  → internal (proxied via Next.js)"
log "  Flower   → SSH tunnel only: ssh -L 5555:localhost:5555 root@13.140.166.97"
log ""
log "GitHub Actions secrets required:"
log "  VPS_SSH_KEY  = content of your deploy private key"
log "  VPS_ENV      = full content of ${ENV_FILE}"
log "========================================================================="
