"""Tests for reactive property chain loop detection."""
import threading
import unittest
from unittest.mock import patch

from app.core.main import reactive_chain
from app.core.main.reactive_chain import chain_enter, chain_exit, chain_format, get_block_reason


class TestReactiveChain(unittest.TestCase):
    def tearDown(self):
        while reactive_chain._get_state() is not None:
            chain_exit()

    def test_linear_chain(self):
        self.assertTrue(chain_enter("A", "p1"))
        self.assertTrue(chain_enter("B", "p2"))
        self.assertEqual(chain_format(), "A.p1 -> B.p2")
        chain_exit()
        chain_exit()
        self.assertEqual(reactive_chain._get_state(), None)

    def test_loop_detection(self):
        self.assertTrue(chain_enter("A", "prop"))
        self.assertTrue(chain_enter("B", "prop"))
        self.assertFalse(chain_enter("A", "prop"))
        self.assertEqual(get_block_reason(), "loop")
        self.assertIn("A.prop", chain_format())
        chain_exit()
        chain_exit()

    def test_depth_overflow(self):
        with patch.object(reactive_chain.Config, "REACTIVE_MAX_DEPTH", 2):
            self.assertTrue(chain_enter("O1", "p"))
            self.assertTrue(chain_enter("O2", "p"))
            self.assertFalse(chain_enter("O3", "p"))
            self.assertEqual(get_block_reason(), "depth")
        chain_exit()
        chain_exit()

    def test_thread_isolation(self):
        results = {}

        def worker():
            self.assertTrue(chain_enter("T", "p"))
            results["chain"] = chain_format()
            chain_exit()

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        self.assertEqual(results["chain"], "T.p")
        self.assertIsNone(reactive_chain._get_state())


if __name__ == "__main__":
    unittest.main()
