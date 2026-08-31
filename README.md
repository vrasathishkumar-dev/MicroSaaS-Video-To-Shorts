# VideoToShorts

> Drop in a long-form broadcast — a stream recording, a webinar, a podcast, a
> conference talk — and get back vertical, captioned, upload-ready YouTube
> Shorts. Transcribed, highlight-scored, enriched with B-roll from Pexels and
> Pixabay, and rendered to YouTube's own recommended upload spec.

---

## How it works

```
 Upload / paste a URL          Background pipeline                Clip library            Export
┌──────────────────────┐   ┌─────────────────────────────┐   ┌────────────────────┐   ┌────────────────┐
│ MP4/MOV/MKV/WebM up  │   │ 1. download   (yt-dlp)      │   │ trim points        │   │ 1080x1920 MP4  │
│ to 2 GB, or a public │──▶│ 2. transcribe (Whisper API) │──▶│ captions           │──▶│ burned-in      │
│ YouTube/Vimeo/etc.   │   │ 3. score highlights         │   │ B-roll in/out      │   │ captions       │
│ video URL            │   │ 4. cluster into 30–50s clips│   │ order              │   │ + poster frame │
└──────────────────────┘   └─────────────────────────────┘   └────────────────────┘   └────────────────┘
```

Every step after submission runs on a **background worker**, never inside a
request handler — a two-hour broadcast can transcribe and render without the
API blocking or timing out.

## Features

- **Broadcast ingest** — direct upload (2 GB cap, streamed to disk) or a URL
  pulled with yt-dlp. URL fetches are SSRF-guarded: every resolved address
  must be public, and redirects are re-validated at each hop.
- **Auto-transcription** — timestamped segments from a Whisper-compatible
  `audio/transcriptions` endpoint. Audio is extracted to 16 kHz mono first, so
  a long broadcast stays well inside the provider's upload limit.
- **Highlight detection** — every transcript segment is scored for engagement;
  adjacent highlights are clustered and padded into 30–50 second windows that
  actually work as a Short, instead of a stranded one-sentence fragment.
- **Automatic B-roll** — keywords extracted from the clip's text drive Pexels
  and Pixabay searches. Every auto-inserted asset stays editable and removable.
- **Clip library** — preview, retrim, reorder, rewrite captions, and manage
  B-roll per clip.
- **Speaker-aware 9:16 reframe** — the crop follows whoever is talking, and
  re-frames at each cut, instead of centre-cropping the gap between two chairs.
- **Upload-ready export** — burned-in time-synced subtitles, B-roll, poster
  frame; see [Video quality](#video-quality) below.
- **Dashboard & admin** — per-user processing stats; platform-wide user
  management for admins.

## Video quality

Exports target [YouTube's recommended upload settings](https://support.google.com/youtube/answer/1722171)
so the clip you download is the clip YouTube publishes, without a lossy
intermediate re-encode.

| Property        | Value                                                      |
|-----------------|------------------------------------------------------------|
| Resolution      | 1080 × 1920 (9:16), square pixels                          |
| Frame rate      | 30 fps, constant                                           |
| Video codec     | H.264 **High** profile, level 4.2, CRF 18, `preset slow`   |
| Pixel format    | `yuv420p`, BT.709 primaries/transfer/matrix                |
| Keyframes       | 2-second GOP (YouTube's recommended interval)              |
| Container       | MP4 with `+faststart` (moov atom first — streams instantly)|
| Audio           | AAC-LC, stereo, 192 kbps, 48 kHz                           |
| Loudness        | Normalised to **−14 LUFS** / −1.5 dBTP                     |

Beyond the container spec, three things do the actual visual work:

**Speaker-aware framing.** A 16:9 broadcast centre-cropped to 9:16 keeps the
middle third of the frame — which, in an interview, is usually the gap between
two people. So the crop window is picked from the footage instead: the clip is
sampled, split into shots at its cuts, and within each shot the column with the
most motion over time is found. On talking-head footage that lands on the
speaker's face. The crop then holds through each shot and jumps only where the
source already cuts, so it reads as framing rather than a camera drifting
around. An interview that intercuts between two chairs gets each person framed
in turn. When no confident subject is found (a montage, a crowd, a hard camera
move) it falls back to `blur` rather than guessing. `RENDER_FRAMING` also
accepts `blur` (blurred fill behind the fitted frame), `crop` (plain
centre-crop) and `pad` (black letterbox).

This needs no ML model or vision dependency — just numpy and the ffmpeg already
required to render. See [`app/services/reframe.py`](backend/app/services/reframe.py).

**Time-synced captions, on any ffmpeg build.** Captions are not one static
block of text pinned over the whole clip: transcript segments overlapping the
clip window are re-timed to the export's own timeline and split into short
readable chunks. Editing a clip's `caption_text` overrides the transcript and
spreads that text across the clip instead.

They are burned in as rasterised PNG overlays (Pillow), composited with plain
`overlay`. That matters because ffmpeg's own text filters are optional at
compile time — `ass`/`subtitles` needs libass, `drawtext` needs libfreetype —
and the default Homebrew ffmpeg on macOS ships neither, which used to produce
a silently uncaptioned Short. Rasterising means captions look identical on a
laptop and in the container. libass and `drawtext` remain as fallbacks if
Pillow or a system font is missing.

**B-roll that actually lands in the export.** Exporting a clip with no B-roll
attached auto-sources it first, so the feature fires by default instead of only
when someone opens the editor and presses the button. The inserted assets are
ordinary rows: they appear in the editor and can be removed or replaced before
a re-export (`BROLL_AUTO_ON_EXPORT=false` turns this off). Providers are asked
for the highest-resolution rendition that fits the canvas, since an upscaled
640×360 stock clip is visibly soft next to CRF 18 footage. `RENDER_BROLL_MODE`
picks an inset `pip` card or a full-frame `fullscreen` cutaway.

**Poster frame.** Every export writes a JPEG poster frame next to the MP4,
served from `GET /api/v1/clips/{id}/thumbnail` — the clip library grid uses it,
and it's a reasonable starting point for a YouTube custom thumbnail.

All of the above is tunable per environment through `RENDER_*` variables — see
[`.env.example`](.env.example).

## Tech stack

| Layer      | Technology                                    |
|------------|-----------------------------------------------|
| Backend    | FastAPI + Python 3.11+                        |
| Frontend   | React 19 + TypeScript + Vite                  |
| Database   | PostgreSQL + SQLAlchemy 2 + Alembic           |
| Queue      | Redis + RQ (dedicated render worker)          |
| Media      | ffmpeg, yt-dlp, Pillow + numpy (framing/captions) |
| Auth       | JWT access/refresh (email + password)         |
| UI         | Tailwind CSS 4 + shadcn/ui + framer-motion    |

## Quick start (Docker)

The compose stack is the production shape: Postgres, Redis, the API, a separate
render worker, and the built frontend behind nginx.

```bash
git clone <repository-url>
cd VideoToShorts
cp .env.example .env

# Required before the stack will start:
#   SECRET_KEY        - long random string, e.g. `openssl rand -hex 32`
#   POSTGRES_PASSWORD - database password
# Recommended: PEXELS_API_KEY, PIXABAY_API_KEY, TRANSCRIPTION_API_KEY

docker compose up -d --build
```

- Frontend → http://localhost:8080
- API + Swagger UI → http://localhost:8000/docs

Database migrations run automatically on API start. The API and the worker
share one `uploads` volume: the worker writes rendered exports, the API streams
them back out.

```bash
docker compose logs -f worker     # watch renders as they happen
docker compose ps                 # health of every service
```

## Local development

### Prerequisites

- Python 3.11+, Node.js 20+, PostgreSQL 15+
- **ffmpeg** on `PATH` (any build — captions and framing don't depend on
  optional ffmpeg components)
- Redis (optional locally; without `REDIS_URL` jobs fall back to FastAPI's own
  background tasks in-process)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload      # http://localhost:8000
```

### Render worker

Only needed when `REDIS_URL` is set. Run it in a second terminal, from the same
virtualenv:

```bash
cd backend
rq worker --url "$REDIS_URL" videotoshorts
```

### Frontend

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

`VITE_API_URL` is inlined at build time, not read at runtime — change it and
rebuild.

## Configuration

Every setting is an environment variable; [`.env.example`](.env.example) is the
complete annotated list. The ones that matter most:

| Variable                | Required        | Notes                                                            |
|-------------------------|-----------------|------------------------------------------------------------------|
| `DATABASE_URL`          | yes             | `postgresql://user:pass@host:5432/videotoshorts`                 |
| `SECRET_KEY`            | yes             | No default anywhere — JWT signing key                            |
| `REDIS_URL`             | in production   | Without it, renders run in the API process and are lost on restart |
| `ALLOWED_ORIGINS`       | in production   | JSON array; must list the origin the frontend is served from      |
| `TRANSCRIPTION_API_KEY` | for transcripts | Whisper-compatible provider                                       |
| `PEXELS_API_KEY` / `PIXABAY_API_KEY` | for B-roll | Sourcing degrades gracefully without them              |
| `RENDER_*`              | no              | Export quality/framing/caption knobs — see [Video quality](#video-quality) |

Access tokens expire in 30 minutes, refresh tokens in 7 days (HS256).

## API

All endpoints live under `/api/v1/`. Interactive docs at `/docs` (Swagger) and
`/redoc`.

| Method | Path                              | Purpose                                  |
|--------|-----------------------------------|------------------------------------------|
| POST   | `/auth/register`, `/auth/login`   | Create a session                         |
| POST   | `/auth/refresh`, `/auth/logout`   | Rotate / revoke the refresh token        |
| GET,PUT| `/auth/me`                        | Current profile                          |
| GET,POST | `/videos`                       | List / submit a broadcast (upload or URL)|
| GET,DELETE | `/videos/{id}`                | Project detail / delete                  |
| POST   | `/videos/{id}/process`            | (Re)run the transcribe + analyse pipeline|
| GET    | `/videos/{id}/transcript`         | Timestamped segments with highlight scores |
| POST   | `/clips/generate`                 | Turn highlights into draft clips         |
| GET    | `/clips`                          | Clip library                             |
| GET,PUT,DELETE | `/clips/{id}`             | Clip detail / edit trim + captions        |
| PATCH  | `/clips/{id}/reorder`             | Reorder within the library               |
| GET    | `/broll/search`                   | Search Pexels + Pixabay                  |
| GET,POST | `/clips/{id}/broll`             | List / insert B-roll on a clip           |
| POST   | `/clips/{id}/broll/auto`          | Auto-source B-roll from clip keywords    |
| DELETE | `/clips/{id}/broll/{broll_id}`    | Remove an inserted asset                 |
| POST   | `/clips/{id}/export`              | Queue the 9:16 render                    |
| GET    | `/clips/{id}/export/status`       | Poll until `ready` or `failed`           |
| GET    | `/clips/{id}/preview`             | Inline playback (`?token=` auth)         |
| GET    | `/clips/{id}/thumbnail`           | Exported poster frame (`?token=` auth)   |
| GET    | `/clips/{id}/download`            | Download the finished MP4                |
| GET    | `/dashboard/stats`                | Per-user counts and storage              |
| GET,PUT| `/admin/users`, `/admin/stats`    | Admin-only                               |

Outside `/api/v1`: `GET /health` is a dependency-free liveness probe;
`GET /ready` checks the database (and Redis when configured) and returns 503
when either is unreachable — point your load balancer at `/ready` and your
orchestrator's restart policy at `/health`.

## Testing

```bash
# Backend — 171 tests, including end-to-end ffmpeg renders
cd backend && source .venv/bin/activate
pytest tests/ -q

# Frontend — 68 tests
cd frontend && npm test
```

Render tests synthesise real MP4s with ffmpeg and assert what actually came
out: the export's resolution, frame rate, profile, audio layout and faststart
flag; that a caption is visibly burned into the lower third (and that a clip
with nothing to say renders clean); and that the crop lands on the moving
subject and steps at a cut. They skip automatically when no ffmpeg binary is
present.

```bash
# Lint / type check
cd backend && ruff check app/ tests/
cd frontend && npm run lint && npm run type-check
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs all of the
above on every push and pull request.

## Production notes

- **Run the worker separately.** Renders are CPU-bound; `preset slow` at CRF 18
  will saturate a core for a while. Scale `worker` replicas independently of
  the API (`docker compose up -d --scale worker=3`).
- **Storage is a shared volume.** The API and every worker must see the same
  `uploads/` filesystem. Uploaded sources and exports are user data and are
  git-ignored — put them on a persistent volume or object store, and set a
  retention policy: a 2 GB source plus its exports adds up fast.
- **Terminate TLS upstream.** The API runs behind `--proxy-headers`; put nginx,
  a load balancer, or your platform's ingress in front of it.
- **Set `ALLOWED_ORIGINS` explicitly** to the frontend's real origin. The
  development default only covers localhost.
- **Faster (lower-quality) renders**, if throughput matters more than fidelity:
  `RENDER_PRESET=medium`, `RENDER_CRF=21`. Roughly halves render time at a
  quality difference most viewers won't notice on a phone.

## Project structure

```
VideoToShorts/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, probes, router wiring
│   │   ├── config.py            # Settings (incl. RENDER_* knobs)
│   │   ├── database.py          # SQLAlchemy engine/session
│   │   ├── models/              # ORM models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── routers/             # API endpoints
│   │   ├── services/
│   │   │   ├── storage.py            # Uploads, yt-dlp, SSRF guards
│   │   │   ├── transcription.py      # Whisper-compatible STT
│   │   │   ├── highlight_detection.py
│   │   │   ├── clip_service.py       # Highlight → clip windows
│   │   │   ├── broll_sourcing.py     # Pexels / Pixabay
│   │   │   ├── video_render.py       # The 9:16 ffmpeg pipeline
│   │   │   └── task_queue.py         # RQ / BackgroundTasks dispatch
│   │   └── auth/                # JWT + rate limiting
│   ├── alembic/                 # Migrations
│   ├── tests/
│   ├── Dockerfile
│   └── docker-entrypoint.sh     # api | worker roles
├── frontend/
│   ├── src/{components,pages,services,context,hooks,types,lib}/
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── .github/workflows/ci.yml
└── .env.example
```

## Roadmap

Not in the MVP, in rough priority order:

- Direct publish to YouTube (OAuth + Data API) — today the flow ends at
  download, by design.
- Word-level caption timing (karaoke highlighting) from a word-timestamped
  transcript. Captions are currently timed per transcript segment and spread
  across their chunks by length.
- Face detection to sharpen the reframe on footage where motion energy is
  ambiguous (several people moving, heavy background activity).
- Object storage (S3/GCS) behind the storage service instead of a local volume.

## License

Private — all rights reserved.
