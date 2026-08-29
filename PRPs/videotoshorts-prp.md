# PRP: VideoToShorts

> Implementation blueprint for parallel agent execution

---

## METADATA

| Field | Value |
|-------|-------|
| **Product** | VideoToShorts |
| **Type** | SaaS |
| **Version** | 1.0 |
| **Created** | 2026-08-29 |
| **Complexity** | High |

---

## PRODUCT OVERVIEW

**Description:** VideoToShorts lets YouTube Shorts creators submit a long-form video — via file upload or a source URL (e.g. a YouTube link) — and automatically turns it into a set of short, vertical (9:16) clips. The pipeline transcribes the audio, detects highlight-worthy moments, burns in captions, and auto-inserts relevant B-roll footage/images from Pexels and Pixabay based on keywords extracted from the content. Finished clips live in a clip library where creators can preview, reorder, re-edit, and export/download them.

**Value Proposition:** Creators currently spend hours manually scrubbing long recordings for shareable moments and sourcing B-roll by hand. VideoToShorts automates the entire repurposing pipeline — highlight detection, captions, and B-roll — turning a single long-form upload into a batch of ready-to-post Shorts in minutes.

**MVP Scope:**
- [ ] User registration and login (email/password)
- [ ] Submit video via file upload or URL
- [ ] AI highlight-moment detection
- [ ] Auto-transcription with burned-in captions
- [ ] Auto B-roll insertion from Pexels/Pixabay (keyword-based)
- [ ] 9:16 export + clip library (preview, reorder, edit, delete, download)

---

## TECH STACK

| Layer | Technology | Skill Reference |
|-------|------------|-----------------|
| Backend | FastAPI + Python 3.11+ | skills/BACKEND.md |
| Frontend | React + TypeScript + Vite | skills/FRONTEND.md |
| Database | PostgreSQL + SQLAlchemy | skills/DATABASE.md |
| Auth | JWT + bcrypt (email/password only) | skills/BACKEND.md |
| UI | Tailwind + shadcn/ui | skills/FRONTEND.md |
| Testing | pytest + RTL | skills/TESTING.md |
| Deployment | Docker + GitHub Actions | skills/DEPLOYMENT.md |
| B-roll | Pexels API + Pixabay API | skills/BACKEND.md |
| Transcription | Whisper / STT service | skills/BACKEND.md |
| Jobs | Background task queue (e.g. Celery/RQ or FastAPI BackgroundTasks + worker) | skills/BACKEND.md, skills/DEPLOYMENT.md |

---

## DATABASE MODELS

### User Model
- id, email, hashed_password, full_name, is_active, is_verified, is_admin, created_at

### RefreshToken Model
- id, user_id (FK → User), token, expires_at, revoked

### VideoProject Model
- id, user_id (FK → User)
- title: str
- source_type: enum(upload, url)
- source_url: str | null
- source_file_path: str | null
- status: enum(pending, downloading, transcribing, analyzing, ready, failed)
- duration_seconds: float | null
- error_message: str | null
- created_at, updated_at

### TranscriptSegment Model
- id, video_project_id (FK → VideoProject)
- start_time: float, end_time: float
- text: str
- is_highlight: bool
- highlight_score: float | null

### Clip Model
- id, video_project_id (FK → VideoProject), user_id (FK → User)
- title: str
- start_time: float, end_time: float
- order_index: int
- status: enum(draft, rendering, ready, failed)
- caption_text: str | null
- video_file_path: str | null
- thumbnail_path: str | null
- created_at, updated_at

### BrollAsset Model
- id, clip_id (FK → Clip)
- source: enum(pexels, pixabay)
- source_asset_id: str
- asset_url: str
- keyword: str
- position_start: float, position_end: float
- created_at

**Relationships:** User 1→N VideoProject; User 1→N RefreshToken; VideoProject 1→N TranscriptSegment; VideoProject 1→N Clip; Clip 1→N BrollAsset

---

## MODULES

### Module 1: Authentication
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /auth/register | Create account |
| POST | /auth/login | Get tokens |
| POST | /auth/refresh | Refresh token |
| POST | /auth/logout | Revoke refresh token |
| GET | /auth/me | Current user |
| PUT | /auth/me | Update profile |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /login | LoginPage | LoginForm |
| /register | RegisterPage | RegisterForm |
| /forgot-password | ForgotPasswordPage | ForgotPasswordForm |
| /profile | ProfilePage | ProfileForm |

---

### Module 2: Video Upload & Processing
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/videos | Submit new video (upload or source_url) |
| GET | /api/videos | List current user's video projects |
| GET | /api/videos/{id} | Get project detail + status |
| DELETE | /api/videos/{id} | Delete project (and its clips) |
| POST | /api/videos/{id}/process | (Re)trigger processing pipeline |
| GET | /api/videos/{id}/transcript | Get transcript segments with highlight flags |

**Backend Services:**
- `services/transcription.py` — calls STT service, stores TranscriptSegments
- `services/highlight_detection.py` — scores/flags highlight-worthy segments

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /videos | VideoListPage | VideoProjectCard, StatusBadge |
| /videos/new | VideoSubmitPage | FileUploadForm, UrlSubmitForm |
| /videos/{id} | VideoDetailPage | TranscriptViewer, HighlightList, GenerateClipsButton |

---

### Module 3: Clip Library
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/clips | List clips (filterable by video_project_id) |
| GET | /api/clips/{id} | Get clip detail |
| PUT | /api/clips/{id} | Edit clip (trim times, caption text) |
| PATCH | /api/clips/{id}/reorder | Reorder clip within its project |
| DELETE | /api/clips/{id} | Delete clip |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /clips | ClipLibraryPage | ClipGrid, ClipCard, ProjectFilter |
| /clips/{id} | ClipEditorPage | VideoPreview, TrimControls, CaptionEditor |

---

### Module 4: B-roll Sourcing
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/clips/{id}/broll/auto | Auto-fetch & insert B-roll from transcript keywords |
| GET | /api/broll/search | Manual search across Pexels/Pixabay |
| POST | /api/clips/{id}/broll | Manually insert a chosen B-roll asset |
| DELETE | /api/clips/{id}/broll/{broll_id} | Remove a B-roll asset |

**Backend Services:**
- `services/broll_sourcing.py` — Pexels + Pixabay API clients, keyword extraction

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| (embedded in /clips/{id}) | BrollPanel | BrollAssetList, BrollSearchModal, SwapButton |

---

### Module 5: Export & Publish
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/clips/{id}/export | Trigger 9:16 render with burned-in captions |
| GET | /api/clips/{id}/export/status | Poll render status |
| GET | /api/clips/{id}/download | Download the finished export |

**Backend Services:**
- `services/video_render.py` — 9:16 render + caption burn-in

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| (embedded in /clips/{id}) | ExportPanel | RenderProgress, DownloadButton |

---

### Module 6: Dashboard
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/dashboard/stats | Videos processed, clips generated, storage used, avg processing time |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /dashboard | DashboardPage | StatsWidget, UsageChart |
| /settings | SettingsPage | AccountSettingsForm |

---

### Module 7: Admin Panel
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /admin/users | List all users |
| PUT | /admin/users/{id} | Update user status (activate/deactivate) |
| GET | /admin/stats | Platform-wide statistics |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /admin | AdminDashboardPage | PlatformStatsWidget |
| /admin/users | AdminUsersPage | UserTable, UserStatusToggle |

---

## PHASE EXECUTION PLAN

**Phase 1: Foundation (4 agents in parallel)**
- DATABASE-AGENT: All 6 models (User, RefreshToken, VideoProject, TranscriptSegment, Clip, BrollAsset), migrations, database.py
- BACKEND-AGENT: main.py, config.py, project structure, background job setup
- FRONTEND-AGENT: Vite setup, folder structure, base components (Tailwind + shadcn/ui)
- DEVOPS-AGENT: Docker, CI/CD, env files, object storage config

**Validation Gate 1:** `pip install`, `alembic upgrade head`, `npm install`, `docker-compose config`

**Phase 2: Modules (backend + frontend parallel per module)**
- Auth Module: JWT endpoints + Login/Register/Profile pages
- Video Upload & Processing: submit/status endpoints + transcription/highlight services + video pages
- Clip Library: CRUD/reorder endpoints + clip library/editor pages
- B-roll Sourcing: Pexels/Pixabay integration endpoints + B-roll panel
- Export & Publish: render endpoints + export panel
- Dashboard: stats endpoint + dashboard/settings pages
- Admin Panel: admin endpoints + admin pages

**Validation Gate 2:** `ruff check backend/`, `mypy backend/`, `npm run lint`, `npm run type-check`

**Phase 3: Quality (3 agents in parallel)**
- TEST-AGENT: pytest + RTL tests, 80%+ coverage across all modules
- REVIEW-AGENT: Security audit (file upload validation, API key handling, auth), performance review of the video pipeline
- RESEARCH-AGENT: Validate Pexels/Pixabay API usage and transcription service integration against current best practices

**Final Validation:** Full test suite, docker build, health checks

---

## VALIDATION GATES

| Gate | Commands |
|------|----------|
| 1 | `alembic upgrade head`, `npm install`, `docker-compose config` |
| 2 | `ruff check backend/`, `npm run type-check` |
| 3 | `pytest --cov --cov-fail-under=80`, `npm test` |
| Final | `docker-compose up -d`, `curl localhost:8000/health` |

---

## ENVIRONMENT VARIABLES

```env
DATABASE_URL=postgresql://user:password@localhost:5432/videotoshorts
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
PEXELS_API_KEY=your-pexels-api-key
PIXABAY_API_KEY=your-pixabay-api-key
TRANSCRIPTION_API_KEY=your-whisper-or-stt-api-key
STORAGE_BUCKET=videotoshorts-media
STORAGE_ACCESS_KEY=xxx
STORAGE_SECRET_KEY=xxx
VITE_API_URL=http://localhost:8000
```

---

## NEXT STEP

Execute with parallel agents:
/execute-prp PRPs/videotoshorts-prp.md
