"""Perf: cascade load без deadlock (PERF_TESTS=1)."""

from __future__ import annotations

import os
import threading
import time
import unittest
from unittest.mock import patch

from app.core.main import reactive_chain
from app.core.main.reactive_chain import chain_enter, chain_exit

RUN = os.environ.get("PERF_TESTS", "").strip().lower() in {"1", "true", "yes"}


@unittest.skipUnless(RUN, "set PERF_TESTS=1 to run performance tests")
class TestReactiveCascadeLoad(unittest.TestCase):
    def tearDown(self):
        while reactive_chain._get_state() is not None:
            chain_exit()

    def test_many_threads_no_deadlock(self):
        errors = []
        barrier = threading.Barrier(16)

        def worker(idx):
            try:
                barrier.wait(timeout=10)
                for depth in range(10):
                    ok = chain_enter(f"T{idx}", f"p{depth}")
                    if not ok:
                        break
                while reactive_chain._get_state() is not None:
                    chain_exit()
            except Exception as ex:
                errors.append(ex)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)
            self.assertFalse(t.is_alive(), "thread deadlocked")
        elapsed = time.perf_counter() - t0
        self.assertEqual(errors, [])
        self.assertIsNone(reactive_chain._get_state())
        self.assertLess(elapsed, 10.0)
        print(f"reactive cascade load elapsed={elapsed:.3f}s")

    def test_depth_overflow_under_load(self):
        with patch.object(reactive_chain.Config, "REACTIVE_MAX_DEPTH", 5):
            count_ok = 0
            for i in range(20):
                if chain_enter("Load", f"p{i}"):
                    count_ok += 1
            self.assertEqual(count_ok, 5)
            while reactive_chain._get_state() is not None:
                chain_exit()


if __name__ == "__main__":
    unittest.main()
