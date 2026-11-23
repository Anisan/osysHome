"""Тесты MonitoredThreadPool: health, overload, shutdown."""

from __future__ import annotations

import threading
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app.core.MonitoredThreadPool import MonitoredThreadPool


class TestMonitoredThreadPool(unittest.TestCase):
    def setUp(self):
        self.pool = MonitoredThreadPool(
            max_workers=2,
            thread_name_prefix="testPool",
            max_queue_size=2,
            task_timeout_threshold=0.2,
            health_check_interval=60.0,
        )

    def tearDown(self):
        self.pool.shutdown(wait=True)

    def test_submit_and_complete(self):
        future = self.pool.submit(lambda: 42, task_id="ok")
        self.assertEqual(future.result(timeout=5), 42)
        stats = self.pool.get_stats()
        self.assertGreaterEqual(stats.completed_tasks, 1)
        self.assertTrue(self.pool.is_healthy())

    def test_queue_overload_rejects(self):
        gate = threading.Event()

        def blocker():
            gate.wait(timeout=5)

        # Заполнить workers + очередь
        futures = []
        for i in range(2):
            futures.append(self.pool.submit(blocker, task_id=f"block-{i}"))
        time.sleep(0.05)
        for i in range(2):
            futures.append(self.pool.submit(lambda: None, task_id=f"queued-{i}"))

        with self.assertRaises(RuntimeError):
            self.pool.submit(lambda: None, task_id="overflow")

        gate.set()
        for fut in futures:
            fut.result(timeout=5)

        self.assertGreaterEqual(self.pool.get_stats().rejected_tasks, 1)

    def test_is_healthy_false_when_all_stuck(self):
        now = datetime.now()
        with self.pool._lock:
            self.pool._active_tasks = {
                "t1": now - timedelta(seconds=10),
                "t2": now - timedelta(seconds=11),
            }
            self.pool._max_workers = 2
            self.pool._task_timeout_threshold = 0.5
        self.assertFalse(self.pool.is_healthy())

    def test_is_healthy_true_if_not_all_stuck(self):
        now = datetime.now()
        with self.pool._lock:
            self.pool._active_tasks = {
                "t1": now - timedelta(seconds=10),
                "t2": now,
            }
            self.pool._max_workers = 2
            self.pool._task_timeout_threshold = 0.5
        self.assertTrue(self.pool.is_healthy())

    def test_shutdown_stops_health_checker(self):
        pool = MonitoredThreadPool(
            max_workers=1,
            thread_name_prefix="shutdownPool",
            max_queue_size=1,
            health_check_interval=60.0,
        )
        pool.shutdown(wait=True)
        self.assertTrue(pool._stop_health_checker.is_set())

    def test_health_checker_resets_unhealthy_executor(self):
        reset_done = threading.Event()
        pool = MonitoredThreadPool(
            max_workers=1,
            thread_name_prefix="resetPool",
            max_queue_size=1,
            task_timeout_threshold=0.05,
            health_check_interval=0.05,
        )
        pool.set_monitoring_callbacks(on_pool_reset=reset_done.set)
        try:
            # gen0 до инжекта «зависшей» задачи — иначе health checker может
            # успеть сбросить пул раньше, и сравнение generation станет flaky.
            gen0 = pool._pool_generation
            with pool._lock:
                pool._active_tasks = {"stuck": datetime.now() - timedelta(seconds=5)}
            self.assertTrue(
                reset_done.wait(timeout=5.0),
                "health checker did not reset unhealthy executor",
            )
            self.assertGreater(pool._pool_generation, gen0)
        finally:
            pool._stop_health_checker.set()
            with pool._lock:
                pool._active_tasks.clear()
            pool.shutdown(wait=True)


if __name__ == "__main__":
    unittest.main()
