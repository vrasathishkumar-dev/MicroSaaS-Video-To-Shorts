#!/usr/bin/env bash
# Runs ON the VPS (invoked by .github/workflows/deploy.yml over SSH).
# Pulls main (the production branch) and brings the docker-compose stack
# up to match it.
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/videotoshorts}"
cd "$APP_DIR"

git fetch origin main
git checkout main
git reset --hard origin/main

docker compose build
docker compose up -d
docker compose exec -T api alembic upgrade head

docker image prune -f
