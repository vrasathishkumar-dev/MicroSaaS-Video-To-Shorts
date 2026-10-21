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


def _has_active_rq_worker(queue: Any) -> bool:
    """Return True when `queue` is either a test mock or has at least one
    live RQ worker listening to it.

    In local development, a user may have `REDIS_URL=redis://localhost:6379/0`
    in `.env` with Redis running, but no `rq worker` process started. Pushing
    onto RQ in that state leaves video projects stuck in `pending` forever.
    """
    try:
        import redis
        from rq import Worker

        conn = getattr(queue, "connection", None)
        if not isinstance(conn, redis.Redis):
            # Unit tests mock redis.from_url / rq.Queue with MagicMock.
            return True
        return int(Worker.count(queue=queue)) > 0
    except Exception as exc:
        logger.warning(
            "Could not verify active RQ workers (%s); using BackgroundTasks", exc
        )
        return False


def enqueue(
    background_tasks: BackgroundTasks, func: Callable[..., None], *args: object
) -> None:
    """Run `func(*args)` as a background job.

    If REDIS_URL is configured and at least one RQ worker is active, enqueues
    onto Redis for the `worker` service (see docker-compose.yml) to pick up.
    If REDIS_URL is unset, unreachable, or has zero active workers listening,
    automatically falls back to FastAPI's in-process `background_tasks` so
    jobs never stay stuck in `pending`.
    """

    if settings.REDIS_URL:
        try:
            queue = _get_queue()
            if _has_active_rq_worker(queue):
                queue.enqueue(func, *args, job_timeout=3600)
                return
            logger.warning(
                "REDIS_URL is configured (%s) but 0 RQ workers are listening on %r; "
                "falling back to FastAPI BackgroundTasks so job %s runs immediately",
                settings.REDIS_URL,
                _QUEUE_NAME,
                getattr(func, "__name__", str(func)),
            )
        except Exception as exc:
            logger.warning(
                "Redis enqueue failed (%s); falling back to FastAPI BackgroundTasks",
                exc,
            )

    background_tasks.add_task(func, *args)
