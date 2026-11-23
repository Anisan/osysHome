"""Resilience реактивной цепочки: concurrent enter/exit, loop, depth."""

from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

from app.core.main import reactive_chain
from app.core.main.reactive_chain import chain_enter, chain_exit, chain_format, get_block_reason


class TestReactiveCascadeResilience(unittest.TestCase):
    def tearDown(self):
        while reactive_chain._get_state() is not None:
            chain_exit()

    def test_concurrent_chains_isolated(self):
        results = {}
        barrier = threading.Barrier(4)

        def worker(idx):
            barrier.wait(timeout=5)
            ok1 = chain_enter(f"O{idx}", "p")
            ok2 = chain_enter(f"O{idx}", "q")
            results[idx] = (ok1, ok2, chain_format())
            chain_exit()
            chain_exit()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(results), 4)
        for idx, (ok1, ok2, fmt) in results.items():
            self.assertTrue(ok1)
            self.assertTrue(ok2)
            self.assertEqual(fmt, f"O{idx}.p -> O{idx}.q")
        self.assertIsNone(reactive_chain._get_state())

    def test_loop_under_nested_pressure(self):
        self.assertTrue(chain_enter("A", "x"))
        self.assertTrue(chain_enter("B", "y"))
        self.assertTrue(chain_enter("C", "z"))
        self.assertFalse(chain_enter("A", "x"))
        self.assertEqual(get_block_reason(), "loop")
        chain_exit()
        chain_exit()
        chain_exit()

    def test_depth_limit_concurrent_attempts(self):
        with patch.object(reactive_chain.Config, "REACTIVE_MAX_DEPTH", 3):
            self.assertTrue(chain_enter("D1", "p"))
            self.assertTrue(chain_enter("D2", "p"))
            self.assertTrue(chain_enter("D3", "p"))
            blocked = []

            def try_enter():
                blocked.append(not chain_enter("D4", "p"))

            threads = [threading.Thread(target=try_enter) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            # В этом же потоке глубина уже 3; другие потоки имеют свою цепочку
            # Главное — основной поток блокируется по depth
            self.assertFalse(chain_enter("D4", "p"))
            self.assertEqual(get_block_reason(), "depth")
            chain_exit()
            chain_exit()
            chain_exit()

    def test_unbalanced_exit_safe(self):
        # лишний exit не должен ронять процесс
        chain_exit()
        self.assertIsNone(reactive_chain._get_state())
        self.assertTrue(chain_enter("X", "p"))
        chain_exit()
        chain_exit()
        self.assertIsNone(reactive_chain._get_state())


if __name__ == "__main__":
    unittest.main()
