"""Perf: поведение MonitoredThreadPool при насыщении (PERF_TESTS=1)."""

from __future__ import annotations

import os
import threading
import time
import unittest

from app.core.MonitoredThreadPool import MonitoredThreadPool

RUN = os.environ.get("PERF_TESTS", "").strip().lower() in {"1", "true", "yes"}


@unittest.skipUnless(RUN, "set PERF_TESTS=1 to run performance tests")
class TestPoolSaturation(unittest.TestCase):
    def test_reject_under_saturation_then_recover(self):
        pool = MonitoredThreadPool(
            max_workers=2,
            thread_name_prefix="perfSat",
            max_queue_size=2,
            task_timeout_threshold=30.0,
            health_check_interval=60.0,
        )
        gate = threading.Event()
        try:
            def blocker():
                gate.wait(timeout=10)

            for i in range(4):
                pool.submit(blocker, task_id=f"b{i}")

            rejected = 0
            for i in range(10):
                try:
                    pool.submit(lambda: None, task_id=f"r{i}")
                except RuntimeError:
                    rejected += 1
            self.assertGreaterEqual(rejected, 1)
            gate.set()
            # После освобождения новые задачи принимаются
            time.sleep(0.1)
            fut = pool.submit(lambda: "ok", task_id="recover")
            self.assertEqual(fut.result(timeout=5), "ok")
            self.assertTrue(pool.is_healthy())
            print(f"pool saturation rejected={rejected} recovered=ok")
        finally:
            gate.set()
            pool.shutdown(wait=True)


if __name__ == "__main__":
    unittest.main()
