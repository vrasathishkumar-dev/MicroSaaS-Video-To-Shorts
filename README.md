# VideoToShorts

> Turn long-form video into ready-to-publish YouTube Shorts — automatically transcribed, highlight-detected, and enriched with B-roll from Pexels and Pixabay.

## Features

- **Auto-Transcription** — Upload a video and get an accurate transcript powered by Whisper / speech-to-text.
- **AI Highlight Detection** — Every transcript segment is scored for engagement; the best moments are flagged as highlights.
- **Automatic B-Roll** — Keywords are extracted from your content and used to fetch relevant stock footage from Pexels and Pixabay.
- **Clip Library** — Preview, reorder, re-edit trim points, edit captions, and manage B-roll for each clip.
- **9:16 Export** — Render vertical shorts with burned-in captions, ready for download.
- **Dashboard** — At-a-glance stats on videos processed, clips generated, and storage used.
- **Admin Panel** — Platform-wide user management and statistics.

## Tech Stack

| Layer      | Technology                        |
|------------|-----------------------------------|
| Backend    | FastAPI + Python 3.11+            |
| Frontend   | React 19 + TypeScript + Vite      |
| Database   | PostgreSQL + SQLAlchemy + Alembic |
| Auth       | JWT (email/password)              |
| UI         | Tailwind CSS 4 + shadcn/ui       |
| Styling    | Glassmorphism + framer-motion     |

## Prerequisites

- **Python 3.11+** with `pip`
- **Node.js 20+** with `npm`
- **PostgreSQL 15+**
- **FFmpeg** (for video rendering)

## Quick Start

### 1. Clone & configure

```bash
git clone <repository-url>
cd VideoToShorts
cp .env.example .env
# Edit .env with your own values (see Environment Variables below)
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head             # Run database migrations
uvicorn app.main:app --reload    # http://localhost:8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

### 4. Docker (alternative)

```bash
docker-compose up -d
```

## Environment Variables

Create a `.env` file at the project root (see `.env.example`):

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/videotoshorts

# Auth
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# B-roll sourcing
PEXELS_API_KEY=your-pexels-api-key
PIXABAY_API_KEY=your-pixabay-api-key

# Storage
UPLOAD_ROOT=./uploads

# Frontend
VITE_API_URL=http://localhost:8000
```

## Development

### Running Tests

```bash
# Backend (121 tests)
cd backend
source .venv/bin/activate
pytest tests/ -v

# Frontend (68 tests)
cd frontend
npm test
```

### Linting

```bash
# Backend
ruff check backend/

# Frontend
cd frontend
npm run lint
```

### Type Checking

```bash
cd frontend
npm run type-check
```

## API Documentation

Once the backend is running, visit:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

All API endpoints are prefixed with `/api/v1/`.

## Project Structure

```
VideoToShorts/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application entrypoint
│   │   ├── config.py            # Settings from env vars
│   │   ├── database.py          # SQLAlchemy session
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── routers/             # API endpoint routers
│   │   ├── services/            # Business logic & integrations
│   │   └── auth/                # Auth utilities & rate limiting
│   ├── alembic/                 # Database migrations
│   ├── tests/                   # pytest test suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/          # React components by module
│   │   ├── pages/               # Route-level page components
│   │   ├── services/            # API client functions
│   │   ├── context/             # React context providers
│   │   ├── hooks/               # Custom React hooks
│   │   ├── types/               # TypeScript interfaces
│   │   └── lib/                 # Utility functions
│   └── package.json
├── docker-compose.yml
└── .env.example
```

## License

Private — all rights reserved.
