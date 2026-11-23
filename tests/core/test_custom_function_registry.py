import unittest
from unittest.mock import patch

from app.core.lib.execute import (
    execute_and_capture_output,
    format_runtime_error,
    get_base_module_environment,
    invalidate_execution_environment_cache,
)
from app.core.main.CustomFunctionRegistry import CustomFunctionRegistry


class TestFormatRuntimeError(unittest.TestCase):
    def test_custom_function_header(self):
        output = (
            'Traceback (most recent call last):\n'
            '  File "<CustomFunction:telegram_helpers>", line 5, in send_telegram_message\n'
            '    callPluginFunction("X", "y", {})\n'
            'RuntimeError: fail\n'
        )
        formatted = format_runtime_error(
            output,
            method_context={'object': 'Hero', 'method': 'poll', 'source': 'self.poll'},
        )
        self.assertIn('CustomFunction «telegram_helpers»', formatted)
        self.assertIn('send_telegram_message', formatted)
        self.assertIn('Строка 5', formatted)
        self.assertIn('Hero', formatted)


class TestCustomFunctionRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = CustomFunctionRegistry()
        invalidate_execution_environment_cache()

    def test_compile_exports_function(self):
        bindings, err = self.registry._compile_one(
            'helpers',
            'def hello():\n    return 42\n',
        )
        self.assertIsNone(err)
        self.assertIn('hello', bindings)
        self.assertTrue(callable(bindings['hello']))

    def test_conflict_detection(self):
        self.registry._rebuild_all([
            {'name': 'a', 'code': 'def foo():\n    pass\n', 'description': ''},
        ])
        ok, err, _bindings = self.registry.validate_exported_symbols(
            'b', 'def foo():\n    pass\n', active=True
        )
        self.assertFalse(ok)
        self.assertIn('foo', err)

    def test_empty_code(self):
        bindings, err = self.registry._compile_one('empty', '')
        self.assertIsNone(err)
        self.assertEqual(bindings, {})

    def test_reload_with_precompiled_skips_recompile(self):
        self.registry._rebuild_all([])
        bindings = {'helper': lambda: 1}
        with patch.object(self.registry, '_compile_one') as mock_compile:
            ok = self.registry._reload_one(
                {'name': 'x', 'code': 'def helper():\n    return 1\n'},
                precompiled=bindings,
            )
        self.assertTrue(ok)
        mock_compile.assert_not_called()
        self.assertIn('helper', self.registry.get_bindings())

    def test_base_environment_cached(self):
        invalidate_execution_environment_cache()
        env1 = get_base_module_environment()
        env2 = get_base_module_environment()
        self.assertIsNot(env1, env2)
        self.assertIn('getProperty', env1)
        self.assertIn('getProperty', env2)


class TestExecuteWithBindings(unittest.TestCase):
    def setUp(self):
        invalidate_execution_environment_cache()

    @patch('app.core.main.CustomFunctionRegistry.custom_function_registry')
    def test_bindings_visible_in_method_code(self, mock_registry):
        def add_one():
            return 1

        mock_registry.get_lsp_revision.return_value = 1
        mock_registry.get_bindings.return_value = {'add_one': add_one}
        output, error = execute_and_capture_output(
            'print(add_one())',
            {'params': None},
            code_filename='<Method:Test.run>',
        )
        self.assertFalse(error)
        self.assertIn('1', output)

    @patch('app.core.main.CustomFunctionRegistry.custom_function_registry')
    def test_error_includes_custom_function_context(self, mock_registry):
        reg = CustomFunctionRegistry()
        reg._rebuild_all([{
            'name': 'telegram_helpers',
            'code': 'def send_telegram_message():\n    raise ValueError("telegram failed")\n',
            'description': '',
        }])
        mock_registry.get_lsp_revision.return_value = reg.get_lsp_revision()
        mock_registry.get_bindings.return_value = reg.get_bindings()
        output, error = execute_and_capture_output(
            'send_telegram_message()',
            {'params': None},
            method_context={'object': 'Godville', 'method': 'poll'},
        )
        self.assertTrue(error)
        self.assertIn('telegram_helpers', output)

    @patch('app.core.main.CustomFunctionRegistry.custom_function_registry')
    def test_runtime_cache_refreshes_on_revision_change(self, mock_registry):
        def version_a():
            return 'a'

        def version_b():
            return 'b'

        mock_registry.get_lsp_revision.return_value = 1
        mock_registry.get_bindings.return_value = {'fn': version_a}
        out1, err1 = execute_and_capture_output('print(fn())', {'params': None})
        self.assertFalse(err1)
        self.assertIn('a', out1)

        mock_registry.get_lsp_revision.return_value = 2
        mock_registry.get_bindings.return_value = {'fn': version_b}
        out2, err2 = execute_and_capture_output('print(fn())', {'params': None})
        self.assertFalse(err2)
        self.assertIn('b', out2)
