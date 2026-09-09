# Deployment Skill

> Docker + Docker Compose + GitHub Actions

---

## Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app
COPY alembic.ini .
COPY ./alembic ./alembic

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

## Nginx Config

```nginx
# frontend/nginx.conf
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
      POSTGRES_DB: ${DB_NAME:-appdb}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      SECRET_KEY: ${SECRET_KEY}
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8000:8000"

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  postgres_data:
```

---

## Environment File

```env
# .env.example
DB_USER=postgres
DB_PASSWORD=securepassword
DB_NAME=appdb
SECRET_KEY=change-me-in-production
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
VITE_API_URL=http://localhost:8000
```

---

## GitHub Actions CI/CD

```yaml
# .github/workflows/ci.yml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Backend Tests
        run: |
          cd backend
          pip install -r requirements.txt
          pytest --cov=app --cov-fail-under=80

      - name: Frontend Tests
        run: |
          cd frontend
          npm ci
          npm test

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - run: docker-compose build
```

---

## Commands

```bash
# Development
docker-compose up -d

# View logs
docker-compose logs -f backend

# Run migrations
docker-compose exec backend alembic upgrade head

# Rebuild
docker-compose build --no-cache

# Stop
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

---

## Best Practices

- Use multi-stage Docker builds
- Run containers as non-root user
- Never store secrets in images
- Use environment variables
- Set up health checks
- Enable HTTPS in production

---

## VPS Deployment (main branch)

`main` is the production branch — there is no separate `prod` branch. Deploy
is CI-triggered, not manual: a push to `main` (only ever from the founder's
manual merge of a `qa → main` PR — see `CLAUDE.md` → Git Branch Policy) runs
`.github/workflows/deploy.yml`, which SSHes into the VPS and runs
`scripts/deploy.sh` there. No SSH credentials are ever handled in a Claude
session.

### One-time VPS setup (founder does this manually)
1. `git clone` this repo to `~/videotoshorts` on the VPS, `git checkout main`.
2. Copy `.env.example` to `.env` in that directory and fill in real values.
3. Add a deploy key (or a dedicated read-only SSH key) so the VPS can
   `git fetch origin main` without a password prompt.
4. Confirm Docker + Docker Compose are installed on the VPS.

### Required GitHub repo secrets
Set these under Settings → Secrets and variables → Actions:
- `VPS_HOST` — the server's IP or hostname
- `VPS_USER` — the SSH user to deploy as
- `VPS_SSH_KEY` — private key with access to that user (paste the key
  contents, never the passphrase)
- `VPS_PORT` — SSH port (usually `22`)

### Rollback
```bash
# On the VPS, in ~/videotoshorts:
git log --oneline -5          # find the last-known-good commit on main
git reset --hard <commit-sha>
docker compose build && docker compose up -d
docker compose exec -T api alembic downgrade -1   # only if that release added a migration
```
Or simpler: revert the bad commit on `main` on GitHub and push — that
re-triggers `deploy.yml` with the reverted code.

---

## VPS Deployment (dev branch — separate environment)

`dev` gets its own environment on the same VPS, entirely separate from
production: its own directory (`~/videotoshorts-dev`), its own docker-compose
project (different directory name ⇒ different container/network/volume
names automatically), its own ports, and its own database — so dev-role
agents merging into `dev` all day never touches the live site. A push to
`dev` (i.e. any dev-role agent's merge — see `CLAUDE.md` → Git Branch
Policy) runs `.github/workflows/deploy-dev.yml`, which runs
`scripts/deploy-dev.sh` on the VPS. Same GitHub secrets as production
(`VPS_HOST`/`VPS_USER`/`VPS_PORT`/`VPS_SSH_KEY`) — same server, different
directory.

### One-time VPS setup
1. `git clone` this repo to `~/videotoshorts-dev` on the VPS, `git checkout dev`.
2. Copy `.env.example` to `.env` there and fill in values that do **not**
   collide with the production stack's ports/DB name — e.g.:
   - `API_PORT` / `WEB_PORT` / `POSTGRES_PORT` — pick ports not already
     bound on the VPS (`ss -ltn` to check).
   - `POSTGRES_DB` — a distinct name, e.g. `videotoshorts_dev`, so the two
     Postgres containers never share data even if ports were reused.
   - `ALLOWED_ORIGINS` / `VITE_API_URL` — must point at the dev ports, not
     production's.
3. Confirm the deploy key already added for production also has read
   access here (same repo, same key works).

### Rollback
Same pattern as production, but in `~/videotoshorts-dev` against `dev`
instead of `main` — a broken `dev` only affects the dev environment, never
the live site.
