"""Tests for app.services.task_queue.

No real Redis is used for either branch: the REDIS_URL-unset path is
exercised against a real BackgroundTasks instance, and the REDIS_URL-set
path mocks rq.Queue.enqueue directly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import BackgroundTasks

from app.config import settings
from app.services import task_queue


def _job(a: int, b: int) -> int:
    return a + b


class TestEnqueue:
    def test_falls_back_to_background_tasks_when_redis_url_unset(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "REDIS_URL", "")
        background_tasks = BackgroundTasks()

        task_queue.enqueue(background_tasks, _job, 1, 2)

        assert len(background_tasks.tasks) == 1
        scheduled = background_tasks.tasks[0]
        assert scheduled.func is _job
        assert scheduled.args == (1, 2)

    def test_enqueues_onto_redis_when_configured(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        # Reset the module-level queue singleton so this test's mock is used
        # instead of a queue potentially cached from a previous test.
        monkeypatch.setattr(task_queue, "_queue", None)

        mock_queue = MagicMock()
        with (
            patch("redis.from_url", return_value=MagicMock()) as mock_from_url,
            patch("rq.Queue", return_value=mock_queue) as mock_queue_cls,
        ):
            background_tasks = BackgroundTasks()
            task_queue.enqueue(background_tasks, _job, 1, 2)

        mock_from_url.assert_called_once_with("redis://localhost:6379/0")
        mock_queue_cls.assert_called_once()
        mock_queue.enqueue.assert_called_once_with(_job, 1, 2)
        # The Redis path must NOT also schedule a BackgroundTask -- that
        # would run the job twice (once in-process, once via the worker).
        assert len(background_tasks.tasks) == 0
