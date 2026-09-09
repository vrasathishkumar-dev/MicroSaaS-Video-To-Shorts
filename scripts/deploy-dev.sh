#!/usr/bin/env bash
# Runs ON the VPS (invoked by .github/workflows/deploy-dev.yml over SSH).
# Pulls dev and brings up a separate docker-compose project so it never
# touches the production stack running out of ~/videotoshorts (main).
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/videotoshorts-dev}"
cd "$APP_DIR"

git fetch origin dev
git checkout dev
git reset --hard origin/dev

docker compose build
docker compose up -d
docker compose exec -T api alembic upgrade head

docker image prune -f
