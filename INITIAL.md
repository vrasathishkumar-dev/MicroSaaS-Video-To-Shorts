# INITIAL.md - VideoToShorts Product Definition

> Turns long-form video into ready-to-publish YouTube Shorts, automatically enriched with B-roll from Pexels and Pixabay.

---

## PRODUCT

### Name
VideoToShorts

### Description
VideoToShorts lets YouTube Shorts creators submit a long-form ("log") video — via file upload or a source URL (e.g. a YouTube link) — and automatically turns it into a set of short, vertical (9:16) clips. The pipeline detects highlight-worthy moments, transcribes the audio, burns in captions, and auto-inserts relevant B-roll footage/images sourced from Pexels and Pixabay based on keywords extracted from the content. Finished clips live in a clip library where creators can preview, reorder, re-edit, and export/download them.

### Target User
YouTube Shorts creators who record long-form video and want an automated way to repurpose it into multiple short clips without manually scrubbing footage or sourcing B-roll themselves.

### Type
- [x] SaaS (Software as a Service)

---

## TECH STACK

### Backend
- [x] FastAPI + Python 3.11+

### Frontend
- [x] React + TypeScript + Vite

### Database
- [x] PostgreSQL (recommended for all stacks)

### Authentication
- [x] Email/Password only

### UI Framework
- [x] Tailwind + shadcn/ui

### Payments
- [ ] None for now (add later if a paid tier is introduced)

### Third-Party APIs
- [x] Pexels API — stock B-roll video/image search
- [x] Pixabay API — stock B-roll video/image search
- [x] Speech-to-text / transcription service (e.g. Whisper) — transcript + caption generation

---

## MODULES

### Module 1: Authentication (Required)

**Description:** User authentication and authorization (email/password only — no OAuth for MVP)

**Models:**
- User: id, email, hashed_password, full_name, is_active, is_verified, is_admin, created_at
- RefreshToken: id, user_id, token, expires_at, revoked

**API Endpoints:**
- POST /auth/register - Create new account
- POST /auth/login - Login with email/password
- POST /auth/refresh - Refresh access token
- POST /auth/logout - Revoke refresh token
- GET /auth/me - Get current user profile
- PUT /auth/me - Update profile

**Frontend Pages:**
- /login - Login page
- /register - Registration page
- /forgot-password - Forgot password page
- /profile - User profile page (protected)

---

### Module 2: Video Upload & Processing

**Description:** Accept a source video via file upload or URL (e.g. YouTube link), then run it through a processing pipeline that transcribes the audio and auto-detects highlight-worthy segments for clipping.

**Models:**
```
VideoProject:
  - id, user_id (FK)
  - title: str
  - source_type: enum(upload, url)
  - source_url: str | null
  - source_file_path: str | null
  - status: enum(pending, downloading, transcribing, analyzing, ready, failed)
  - duration_seconds: float | null
  - error_message: str | null
  - created_at, updated_at

TranscriptSegment:
  - id, video_project_id (FK)
  - start_time: float
  - end_time: float
  - text: str
  - is_highlight: bool  # flagged by AI highlight-detection
  - highlight_score: float | null
```

**API Endpoints:**
```
POST   /api/videos                 - Submit new video (file upload or source_url)
GET    /api/videos                 - List current user's video projects
GET    /api/videos/{id}            - Get project detail + status
DELETE /api/videos/{id}            - Delete project (and its clips)
POST   /api/videos/{id}/process    - (Re)trigger processing pipeline
GET    /api/videos/{id}/transcript - Get transcript segments (with highlight flags)
```

**Frontend Pages:**
- /videos - List of submitted video projects with processing status
- /videos/new - Submit a new video (file upload or paste URL)
- /videos/{id} - Project detail: status, transcript, detected highlight segments, "generate clips" action

---

### Module 3: Clip Library

**Description:** Manage the short clips generated from a video project's highlight segments — preview, reorder, re-edit trim points/captions, and delete.

**Models:**
```
Clip:
  - id, video_project_id (FK), user_id (FK)
  - title: str
  - start_time: float
  - end_time: float
  - order_index: int
  - status: enum(draft, rendering, ready, failed)
  - caption_text: str | null
  - video_file_path: str | null
  - thumbnail_path: str | null
  - created_at, updated_at
```

**API Endpoints:**
```
GET    /api/clips                  - List clips (filterable by video_project_id)
GET    /api/clips/{id}             - Get clip detail
PUT    /api/clips/{id}             - Edit clip (trim times, caption text)
PATCH  /api/clips/{id}/reorder     - Reorder clip within its project
DELETE /api/clips/{id}             - Delete clip
```

**Frontend Pages:**
- /clips - Clip library (grid/list of all clips, filter by project)
- /clips/{id} - Clip editor: preview, adjust trim points, edit captions, manage B-roll, export

---

### Module 4: B-roll Sourcing

**Description:** Automatically extract keywords from a clip's transcript/content and fetch matching B-roll footage/images from Pexels and Pixabay, inserting them into the clip timeline.

**Models:**
```
BrollAsset:
  - id, clip_id (FK)
  - source: enum(pexels, pixabay)
  - source_asset_id: str
  - asset_url: str
  - keyword: str
  - position_start: float
  - position_end: float
  - created_at
```

**API Endpoints:**
```
POST   /api/clips/{id}/broll/auto        - Auto-fetch & insert B-roll based on transcript keywords
GET    /api/broll/search?q=&source=      - Manual search across Pexels/Pixabay
POST   /api/clips/{id}/broll             - Manually insert a chosen B-roll asset
DELETE /api/clips/{id}/broll/{broll_id}  - Remove a B-roll asset from the clip
```

**Frontend Pages:**
- (Embedded in /clips/{id} clip editor) - B-roll panel showing auto-inserted assets with swap/remove controls

---

### Module 5: Export & Publish

**Description:** Render the final clip in 9:16 vertical format with captions burned in, and make it available for download. No auto-publish to YouTube in MVP.

**API Endpoints:**
```
POST   /api/clips/{id}/export         - Trigger 9:16 render with burned-in captions
GET    /api/clips/{id}/export/status  - Poll render status
GET    /api/clips/{id}/download       - Download the finished export
```

**Frontend Pages:**
- (Embedded in /clips/{id} clip editor) - Export button + render progress + download link

---

### Module 6: Dashboard

**Description:** Overview of usage — videos processed, clips generated, processing time — and account settings.

**API Endpoints:**
```
GET /api/dashboard/stats - Videos processed, clips generated, storage used, avg processing time
```

**Frontend Pages:**
- /dashboard - Main dashboard with usage widgets and stats
- /settings - User settings and preferences

---

### Module 7: Admin Panel

**Description:** Admin-only management interface for users and platform stats.

**API Endpoints:**
- GET /admin/users - List all users
- PUT /admin/users/{id} - Update user status (activate/deactivate)
- GET /admin/stats - Platform-wide statistics (total users, videos, clips)

**Frontend Pages:**
- /admin - Admin dashboard (protected, admin only)
- /admin/users - User management

---

## MVP SCOPE

### Must Have (MVP)
- [x] User registration and login (email/password)
- [x] Submit video via file upload or URL
- [x] AI highlight-moment detection
- [x] Auto-transcription with burned-in captions
- [x] Auto B-roll insertion from Pexels/Pixabay (keyword-based)
- [x] 9:16 export + clip library (preview, reorder, edit, delete, download)

### Nice to Have (Post-MVP)
- [ ] Manual B-roll search & override UI
- [ ] Analytics dashboard (usage metrics)
- [ ] Admin panel
- [ ] Direct publish to YouTube via API
- [ ] Google OAuth login

---

## ACCEPTANCE CRITERIA

### Authentication
- [ ] User can register with email/password
- [ ] User can login with email/password
- [ ] JWT tokens work correctly with refresh
- [ ] Protected routes redirect to login

### Video Upload & Processing
- [ ] User can submit a video via file upload
- [ ] User can submit a video via source URL
- [ ] Pipeline transcribes audio and stores transcript segments
- [ ] Pipeline flags highlight-worthy segments with a score
- [ ] Project status updates correctly through the pipeline stages

### Clip Library
- [ ] Clips are generated from flagged highlight segments
- [ ] User can preview, reorder, edit trim points/captions, and delete clips

### B-roll Sourcing
- [ ] Auto B-roll insertion fetches relevant assets from Pexels/Pixabay based on keywords
- [ ] User can remove or swap an inserted B-roll asset

### Export & Publish
- [ ] Clip renders in 9:16 with burned-in captions
- [ ] User can download the finished export

### Quality
- [ ] All API endpoints documented in OpenAPI
- [ ] Backend test coverage 80%+
- [ ] Frontend TypeScript strict mode passes
- [ ] Docker builds and runs successfully

---

## SPECIAL REQUIREMENTS

### Security
- [x] Rate limiting on auth endpoints
- [x] Input validation on all endpoints
- [x] SQL injection prevention
- [x] XSS prevention
- [x] File upload validation (type/size limits on video uploads)

### Integrations
- [x] Pexels API for B-roll sourcing
- [x] Pixabay API for B-roll sourcing
- [x] Transcription service (e.g. Whisper) for transcript/captions
- [ ] Email service for notifications (post-MVP)
- [ ] Stripe/payments (not needed for MVP)

### Infrastructure
- [x] Background job processing for video pipeline (transcription, highlight detection, rendering) — long-running tasks should not block API requests
- [x] Object storage for source videos, generated clips, and thumbnails

---

## AGENTS

> These 6 agents will build your product in parallel:

| Agent | Role | Works On |
|-------|------|----------|
| DATABASE-AGENT | Creates all models and migrations | All database models |
| BACKEND-AGENT | Builds API endpoints and services | All modules' backends |
| FRONTEND-AGENT | Creates UI pages and components | All modules' frontends |
| DEVOPS-AGENT | Sets up Docker, CI/CD, environments | Infrastructure |
| TEST-AGENT | Writes unit and integration tests | All code |
| REVIEW-AGENT | Security and code quality audit | All code |

---

# READY?

```bash
/generate-prp INITIAL.md
```

Then:

```bash
/execute-prp PRPs/videotoshorts-prp.md
```
