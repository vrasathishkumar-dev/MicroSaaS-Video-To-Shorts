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

## Agent Coordination — the virtual team

VideoToShorts runs as a one-person company (see `AI Virtual Team
Playbook.md`). The founder is the only human; every functional role is a
Claude Code subagent defined in `.claude/agents/`, dispatched via the Agent
tool by the main session, which acts as the orchestrator/founder liaison.

**Treat a new feature idea, requirement, or piece of feedback from the
founder as the start of the pipeline** — not every message. Ordinary
questions, direct instructions ("fix this", "run the tests"), and follow-ups
on work already in flight are handled directly, same as any other session.

Pipeline:
```
Idea/feedback → ba (backlog + story) → designer (spec) → backend-agent /
frontend-agent / database-agent (build) → tester (QA) → devops (deploy)
→ seo-geo + marketer (visibility & launch)
```

Roster (`.claude/agents/*.md`):
- `ba` — Business Analyst: idea/feedback → prioritized backlog story
- `designer` — UX/UI spec (no code)
- `backend-agent` / `frontend-agent` / `database-agent` — implementation
- `tester` — QA: test plan, execution, pass/fail (doesn't fix bugs)
- `devops` — CI/CD, deploy, rollback plan
- `seo-geo` — SEO (organic ranking) + GEO (AI-synthesized-answer visibility)
  + AEO (direct question/answer surfaces: featured snippets, FAQ schema)
- `marketer` — launch copy, campaign plan, channels

**Shared knowledge base**: `team/backlog.md` — every role reads the story
it's working on there and appends its own handoff subsection, so no role
re-asks a prior role's questions.

**Governance — two approval gates, everything else runs on:**
1. After `ba` drafts a story (founder approves scope) — do not start
   `designer`/build until approved.
2. After `tester` signs off (founder approves release) — do not dispatch
   `devops` until approved.
