"""Server-Sent Events router for real-time clip render progress.

Owned by BACKEND-AGENT (Export & Publish module). Provides a streaming
endpoint that the frontend subscribes to when a clip starts rendering,
replacing the 3-second setInterval polling loop with a push-based update.

Design notes:
- Uses a simple DB-poll loop (every 1.5s) rather than Redis Pub/Sub to
  keep the dependency surface minimal. Redis Pub/Sub would be marginally
  more efficient but adds a second async connection, whereas the polling
  loop is 1-2 queries per second per active render -- negligible for
  personal use.
- The endpoint never blocks; it yields events as a generator and FastAPI
  streams them via `StreamingResponse`.
- Authentication uses the same `?token=` bearer approach as the download
  endpoint -- EventSource in the browser cannot set custom headers, so the
  JWT must ride the query string.
- The stream closes automatically when the clip reaches a terminal status
  (`ready` or `failed`) or when the client disconnects.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.dependencies import get_current_user_for_media, get_db
from app.models.clip import Clip, ClipStatus
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clips", tags=["events"])

# How often to poll the DB for a status change while a clip is rendering.
_POLL_INTERVAL_SECONDS = 1.5

# Maximum time (seconds) a stream stays open without a terminal event.
# Safeguard against a render job that died silently without updating the DB.
_MAX_STREAM_SECONDS = 900  # 15 minutes -- more than enough for any clip


def _progress_pct(status: ClipStatus) -> int:
    """Map a clip status to a rough integer progress percentage.

    This is an approximation: we don't instrument ffmpeg subprocess progress
    here (that would require parsing ffmpeg's stderr in real time). Instead
    we map lifecycle states to representative waypoints so the progress bar
    moves meaningfully rather than jumping 0 → 100.
    """
    return {
        ClipStatus.draft: 0,
        ClipStatus.rendering: 40,
        ClipStatus.ready: 100,
        ClipStatus.failed: 0,
    }.get(status, 0)


async def _clip_event_stream(
    clip_id: int,
    user_id: int,
    db: Session,
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted status update events until the clip is done."""

    elapsed = 0.0

    # Validate ownership once up front; after that, re-fetch the clip every
    # poll so we always see the freshest status without keeping a long-lived
    # DB transaction open.
    clip = db.query(Clip).filter(Clip.id == clip_id, Clip.user_id == user_id).first()
    if clip is None:
        yield _sse_event(
            {"type": "error", "message": "Clip not found or access denied"}
        )
        return

    # Send an immediate snapshot so the client doesn't have to wait for the
    # first poll interval before seeing any data.
    yield _sse_event(
        {
            "type": "status_update",
            "status": clip.status.value,
            "pct": _progress_pct(clip.status),
            "virality_score": clip.virality_score,
        }
    )

    terminal = {ClipStatus.ready, ClipStatus.failed}

    if clip.status in terminal:
        return

    while elapsed < _MAX_STREAM_SECONDS:
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        elapsed += _POLL_INTERVAL_SECONDS

        # Re-fetch from DB -- the RQ worker writes to a separate process.
        db.expire(clip)
        db.refresh(clip)

        pct = _progress_pct(clip.status)

        yield _sse_event(
            {
                "type": "status_update",
                "status": clip.status.value,
                "pct": pct,
                "virality_score": clip.virality_score,
            }
        )

        if clip.status in terminal:
            # One final event already sent above; close the stream.
            return

    # Timed out -- tell the client so it can fall back to manual polling.
    yield _sse_event({"type": "timeout", "message": "Stream timed out; poll manually."})


def _sse_event(data: dict) -> str:
    """Format a dict as an SSE `data:` line, followed by a blank line."""
    return f"data: {json.dumps(data)}\n\n"


@router.get("/{clip_id}/events")
async def clip_events(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_for_media),
) -> StreamingResponse:
    """SSE stream for real-time render progress on a single clip.

    The frontend connects here immediately after triggering an export and
    receives `status_update` events as the render progresses:

        data: {"type": "status_update", "status": "rendering", "pct": 40}
        data: {"type": "status_update", "status": "ready", "pct": 100}

    Authentication: JWT via `?token=<access_token>` (EventSource cannot
    set Authorization headers; see get_current_user_for_media).

    The stream closes automatically when `status` is `ready` or `failed`,
    or after 15 minutes (safeguard against a silently-failed render job).
    """
    return StreamingResponse(
        _clip_event_stream(clip_id, current_user.id, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx response buffering
        },
    )
