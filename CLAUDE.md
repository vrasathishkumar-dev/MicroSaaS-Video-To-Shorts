# CLAUDE.md - VideoToShorts Project Rules

> Project-specific rules for Claude Code. This file is read automatically.

---

## Project Overview

**Project Name:** VideoToShorts
**Description:** Turns long-form video into ready-to-publish YouTube Shorts, automatically enriched with B-roll from Pexels and Pixabay.
**Tech Stack:**
- Backend: FastAPI + Python 3.11+
- Frontend: React + TypeScript + Vite
- Database: PostgreSQL + SQLAlchemy
- Auth: JWT (email/password only)
- UI: Tailwind + shadcn/ui

---

## Project Structure

```
videotoshorts/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── video_project.py
│   │   │   ├── transcript_segment.py
│   │   │   ├── clip.py
│   │   │   └── broll_asset.py
│   │   ├── schemas/
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── videos.py
│   │   │   ├── clips.py
│   │   │   ├── broll.py
│   │   │   ├── dashboard.py
│   │   │   └── admin.py
│   │   ├── services/
│   │   │   ├── transcription.py    # Whisper/STT integration
│   │   │   ├── highlight_detection.py
│   │   │   ├── broll_sourcing.py   # Pexels/Pixabay clients
│   │   │   └── video_render.py     # 9:16 export + caption burn-in
│   │   └── auth/
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   │   ├── videos/
│   │   │   ├── clips/
│   │   │   ├── dashboard/
│   │   │   └── admin/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── context/
│   │   └── types/
│   └── package.json
├── .claude/
│   └── commands/
├── skills/
├── agents/
└── PRPs/
```

---

## Code Standards

### Python (Backend)
```python
# ALWAYS use type hints
def get_video_project(db: Session, project_id: int) -> VideoProject:
    pass

# ALWAYS add docstrings for public functions
def create_clip(db: Session, data: ClipCreate) -> Clip:
    """
    Create a new clip from a video project's highlight segment.

    Args:
        db: Database session
        data: Clip creation data

    Returns:
        Created Clip object
    """
    pass
```

### TypeScript (Frontend)
```typescript
// ALWAYS define interfaces for props and data
interface ClipProps {
  id: number;
  videoProjectId: number;
  startTime: number;
  endTime: number;
  status: "draft" | "rendering" | "ready" | "failed";
}

// NO any types allowed
const fetchClip = async (id: number): Promise<Clip> => {
  // ...
};
```

---

## Forbidden Patterns

### Backend
- ❌ Never use `print()` - use `logging` module
- ❌ Never store passwords in plain text
- ❌ Never hardcode secrets (Pexels/Pixabay API keys included) - use environment variables
- ❌ Never use `SELECT *` - specify columns
- ❌ Never skip input validation
- ❌ Never run video processing (transcription, rendering) synchronously inside a request handler - use background jobs

### Frontend
- ❌ Never use `any` type
- ❌ Never leave console.log in production
- ❌ Never skip error handling in async operations
- ❌ Never use inline styles - use Tailwind

---

## Module-Specific Rules

### Video Upload & Processing
- Every `VideoProject` must belong to a user (`user_id` foreign key)
- `status` must be one of: `pending`, `downloading`, `transcribing`, `analyzing`, `ready`, `failed`
- File uploads must be validated for type and size before being queued for processing
- URL submissions must validate the URL is reachable before queuing

### Clip Library
- Every `Clip` must belong to a `VideoProject` and a `user_id`
- `status` must be one of: `draft`, `rendering`, `ready`, `failed`
- `start_time`/`end_time` must fall within the parent video's duration

### B-roll Sourcing
- `source` must be one of: `pexels`, `pixabay`
- Auto-insertion must always be re-editable/removable by the user — never lock in an automatic choice

### Export & Publish
- Exports must render in 9:16 aspect ratio with captions burned in
- No auto-publish to YouTube in MVP — download only

---

## API Conventions

- All endpoints prefixed with `/api/v1/`
- Use plural nouns for resources: `/videos`, `/clips`
- Return appropriate HTTP status codes:
  - 200: Success
  - 201: Created
  - 400: Bad Request
  - 401: Unauthorized
  - 404: Not Found
  - 409: Conflict

---

## Authentication

Email/password only for MVP (no OAuth).

### JWT Configuration
- Access token expires: 30 minutes
- Refresh token expires: 7 days
- Algorithm: HS256

---

## Environment Variables

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

# Transcription
TRANSCRIPTION_API_KEY=your-whisper-or-stt-api-key

# Storage
STORAGE_BUCKET=videotoshorts-media
STORAGE_ACCESS_KEY=xxx
STORAGE_SECRET_KEY=xxx

# Frontend
VITE_API_URL=http://localhost:8000
```

---

## Development Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Docker
docker-compose up -d

# Tests
pytest backend/tests -v
cd frontend && npm test

# Linting
ruff check backend/
cd frontend && npm run lint
```

---

## Commit Message Format

```
feat([module]): add [feature]
fix([module]): fix [bug]
refactor([module]): refactor [component]
test([module]): add tests for [feature]
docs: update [documentation]
```

---

## Skills Reference

| Task | Skill to Read |
|------|---------------|
| Database models | skills/DATABASE.md |
| API + Auth | skills/BACKEND.md |
| React + UI | skills/FRONTEND.md |
| Testing | skills/TESTING.md |
| Deployment | skills/DEPLOYMENT.md |

---

## Agent Coordination

For complex tasks, the ORCHESTRATOR coordinates:
- DATABASE-AGENT → Backend models
- BACKEND-AGENT → API development
- FRONTEND-AGENT → UI components
- TEST-AGENT → Testing
- REVIEW-AGENT → Code review
- DEVOPS-AGENT → Deployment

Read agent definitions in `/agents/` folder.
