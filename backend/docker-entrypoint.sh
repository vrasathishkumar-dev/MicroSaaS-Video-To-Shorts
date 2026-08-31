#!/usr/bin/env bash
# Container entrypoint for both roles of the backend image.
#
#   api     -- run migrations, then serve the FastAPI app
#   worker  -- consume render/transcode jobs off the Redis queue
#
# Migrations run only in the api role so two containers never race to take
# alembic's lock on the same database.
set -euo pipefail

role="${1:-api}"
shift || true

case "${role}" in
  api)
    echo "Applying database migrations..."
    alembic upgrade head
    exec uvicorn app.main:app \
      --host 0.0.0.0 \
      --port 8000 \
      --workers "${WEB_CONCURRENCY:-4}" \
      --proxy-headers \
      --forwarded-allow-ips '*'
    ;;
  worker)
    : "${REDIS_URL:?worker role requires REDIS_URL}"
    exec rq worker --url "${REDIS_URL}" videotoshorts
    ;;
  *)
    exec "${role}" "$@"
    ;;
esac
