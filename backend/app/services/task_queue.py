"""Background job dispatch: real Redis queue in production, BackgroundTasks locally.

Two job types exist in this app: `run_process_video_project` (video
download/transcribe/highlight pipeline) and `render_clip` (ffmpeg export).
Both are single importable functions that open their own DB session, which
is exactly RQ's model -- no broker/routing complexity needed beyond that.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import BackgroundTasks

from app.config import settings

logger = logging.getLogger(__name__)

_QUEUE_NAME = "videotoshorts"

_queue: Any = None


def _get_queue() -> Any:
    """Lazily build the RQ Queue, so `redis`/`rq` are only ever imported
    (and a connection only ever attempted) when REDIS_URL is actually set."""

    global _queue
    if _queue is None:
        import redis
        from rq import Queue

        connection = redis.from_url(settings.REDIS_URL)
        _queue = Queue(_QUEUE_NAME, connection=connection)
    return _queue


def enqueue(
    background_tasks: BackgroundTasks, func: Callable[..., None], *args: object
) -> None:
    """Run `func(*args)` as a background job.

    If REDIS_URL is configured, enqueues onto Redis for the `worker`
    service (see docker-compose.yml) to pick up -- this is how production
    should run, so heavy video/render work never shares the API process's
    resources and survives an API restart.

    If REDIS_URL is not configured (local dev; always true in the test
    suite, which doesn't want a real Redis dependency), falls back to
    FastAPI's own `background_tasks`, run after the response is sent --
    the exact timing/semantics this app already relied on before the queue
    existed. This fallback is deliberate, not just a stand-in: the caller's
    DB session (e.g. right after `db.refresh(...)`) is often still open at
    this point, and `func` opens its *own* session -- running it inline
    here instead of after the response risks two live sessions competing
    for the same connection (acute on the test suite's shared-connection
    SQLite `StaticPool`). BackgroundTasks avoids that by construction.
    """

    if settings.REDIS_URL:
        _get_queue().enqueue(func, *args)
        return

    background_tasks.add_task(func, *args)
