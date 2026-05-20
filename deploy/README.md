# bitPredict — Production Deployment

Deployed to VPS `72.62.96.223` (Hostinger, Ubuntu 24.04).

## Layout on the server

```
/opt/bitpredict/                  # cloned repo
├── docker-compose.prod.yml       # production compose file
├── .env.production               # secrets (NOT in git)
└── deploy/
    ├── setup.sh                  # first-time bootstrap
    └── deploy.sh                 # pull + build + restart
```

## Ports (deliberately picked to avoid clashing with neighbouring apps)

| Service  | Host port | Inside container |
|----------|-----------|------------------|
| Frontend | **3005**  | 3000             |
| Backend  | **8004**  | 8000             |
| Flower   | **5556**  | 5555             |
| DB       | —         | 5432 (internal)  |
| Redis    | —         | 6379 (internal)  |

## First-time setup

On the VPS as root:

```bash
curl -sSL https://raw.githubusercontent.com/leopbar/bitPredict/main/deploy/setup.sh | sudo bash
```

This clones the repo, generates random secrets, builds the images, and starts everything.

## Continuous deployment

Every push to `main` triggers `.github/workflows/deploy.yml`, which SSHes into the VPS and runs `deploy.sh`.

### Required GitHub secrets

| Secret            | Value                                                                |
|-------------------|----------------------------------------------------------------------|
| `SSH_HOST`        | `72.62.96.223`                                                       |
| `SSH_USER`        | `root`                                                               |
| `SSH_PRIVATE_KEY` | Contents of the deploy private key (paired with the server's authorized_keys) |

## Manual operations

```bash
# Tail backend logs
docker logs -f bitpredict-backend

# Run a one-off Alembic migration
cd /opt/bitpredict
docker compose -f docker-compose.prod.yml --env-file .env.production exec backend alembic upgrade head

# Full restart
bash /opt/bitpredict/deploy/deploy.sh

# Tail deploy log
tail -f /var/log/bitpredict-deploy.log
```
