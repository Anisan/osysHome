"""Отказоустойчивость execute_and_capture_output: exception, пустой код, изоляция."""

from __future__ import annotations

import unittest

from app.core.lib.execute import compile_method_code, execute_and_capture_output


class TestExecuteFaults(unittest.TestCase):
    def test_empty_code_ok(self):
        output, err = execute_and_capture_output("", {})
        self.assertFalse(err)
        self.assertEqual(output, "")

    def test_exception_captured_not_raised(self):
        output, err = execute_and_capture_output("raise ValueError('boom')", {})
        self.assertTrue(err)
        self.assertIn("boom", output)
        self.assertIn("ValueError", output)

    def test_toplevel_return_allowed(self):
        code = "x = 1\nreturn x"
        compiled = compile_method_code(code)
        # exec wrapper stores nothing into locals of caller; just ensure compile works
        self.assertIsNotNone(compiled)
        output, err = execute_and_capture_output("print(1)\nreturn 2", {})
        self.assertFalse(err)
        self.assertIn("1", output)

    def test_syntax_error_captured(self):
        output, err = execute_and_capture_output("def (\n", {})
        self.assertTrue(err)
        self.assertIn("error", output.lower())

    def test_method_context_in_error(self):
        output, err = execute_and_capture_output(
            "raise RuntimeError('x')",
            {},
            method_context={"object": "Lamp", "method": "onChange", "source": "test"},
        )
        self.assertTrue(err)
        self.assertIn("Lamp", output)
        self.assertIn("onChange", output)

    def test_variables_available(self):
        output, err = execute_and_capture_output("print(params['v'])", {"params": {"v": 7}})
        self.assertFalse(err)
        self.assertIn("7", output)

    def test_exception_does_not_break_next_call(self):
        _, err1 = execute_and_capture_output("raise RuntimeError('a')", {})
        self.assertTrue(err1)
        output, err2 = execute_and_capture_output("print('ok')", {})
        self.assertFalse(err2)
        self.assertIn("ok", output)


if __name__ == "__main__":
    unittest.main()
