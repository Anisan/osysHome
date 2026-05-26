import io
import re
import sys
import threading
import traceback
from typing import Any, Dict, Optional, Tuple

MODULE_NAMES = [
    "app.core.lib.common",
    "app.core.lib.constants",
    "app.core.lib.object",
    "app.core.lib.cache",
    "app.core.lib.sql",
]

_CUSTOM_FUNCTION_FRAME_RE = re.compile(
    r'File "<CustomFunction:([^>]+)>", line (\d+), in (\w+)'
)

_env_lock = threading.RLock()
_base_environment: Optional[Dict[str, Any]] = None
_runtime_environment: Optional[Dict[str, Any]] = None
_runtime_cf_revision: int = -1


def invalidate_execution_environment_cache() -> None:
    """Drop merged runtime env; base module imports stay cached."""
    global _runtime_environment, _runtime_cf_revision
    with _env_lock:
        _runtime_environment = None
        _runtime_cf_revision = -1


def _build_base_module_environment() -> Dict[str, Any]:
    """Build execution environment with standard module imports (no CustomFunction)."""
    environment = globals().copy()
    for module_name in MODULE_NAMES:
        import_statement = f'from {module_name} import *'
        exec(import_statement, environment)
    return environment


def get_base_module_environment() -> Dict[str, Any]:
    """Cached standard imports only — for CustomFunction compile/validate."""
    global _base_environment
    with _env_lock:
        if _base_environment is None:
            _base_environment = _build_base_module_environment()
        return dict(_base_environment)


def build_module_environment() -> Dict[str, Any]:
    """Backward-compatible alias: base imports only, no CustomFunction bindings."""
    return get_base_module_environment()


def _get_runtime_environment() -> Dict[str, Any]:
    """Cached base + CustomFunction bindings; refreshed on registry revision change."""
    global _base_environment, _runtime_environment, _runtime_cf_revision

    from app.core.main.CustomFunctionRegistry import custom_function_registry

    revision = custom_function_registry.get_lsp_revision()
    with _env_lock:
        if _base_environment is None:
            _base_environment = _build_base_module_environment()
        if _runtime_environment is None or _runtime_cf_revision != revision:
            merged = dict(_base_environment)
            merged.update(custom_function_registry.get_bindings())
            _runtime_environment = merged
            _runtime_cf_revision = revision
        return _runtime_environment


def format_runtime_error(
    output: str,
    method_context: Optional[dict] = None,
) -> str:
    """Prepend human-readable CustomFunction / method context to error output."""
    if '<CustomFunction:' not in output:
        if method_context:
            header = ['--- Контекст вызова ---']
            if method_context.get('object'):
                header.append(f"Объект: {method_context['object']}")
            if method_context.get('method'):
                header.append(f"Метод: {method_context['method']}")
            if method_context.get('owner'):
                header.append(f"Владелец метода: {method_context['owner']}")
            if method_context.get('source'):
                header.append(f"Источник: {method_context['source']}")
            return "\n".join(header) + "\n\n" + output
        return output

    cf_name = None
    fn_name = None
    error_line = None
    for line in output.splitlines():
        match = _CUSTOM_FUNCTION_FRAME_RE.search(line)
        if match:
            cf_name = match.group(1)
            error_line = match.group(2)
            fn_name = match.group(3)
            break

    header = []
    if cf_name:
        header.append(f"=== Ошибка в CustomFunction «{cf_name}» ===")
        if fn_name:
            header.append(f"Функция: {fn_name}")
        if error_line:
            header.append(f"Строка {error_line} в <CustomFunction:{cf_name}>")

    if method_context:
        header.append('')
        header.append('--- Контекст вызова ---')
        if method_context.get('object'):
            header.append(f"Объект: {method_context['object']}")
        if method_context.get('method'):
            header.append(f"Метод: {method_context['method']}")
        if method_context.get('owner'):
            header.append(f"Владелец метода: {method_context['owner']}")
        if method_context.get('source'):
            header.append(f"Источник: {method_context['source']}")

    if header:
        return "\n".join(header) + "\n\n" + output
    return output


def execute_and_capture_output(
    code: str,
    variables: dict,
    code_filename: str = '<string>',
    method_context: Optional[dict] = None,
) -> Tuple[str, bool]:
    """Execute Python code with provided variables and capture output/errors.

    Args:
        code: Python source to run.
        variables: Locals/globals overlay (self, params, etc.).
        code_filename: Virtual filename for compile/traceback.
        method_context: Optional dict for format_runtime_error on failure.

    Returns:
        Captured output (possibly formatted) and error flag.
    """
    if not code:
        return "", False

    try:
        environment = dict(_get_runtime_environment())
    except Exception as e:
        return f"Failed to build environment: {str(e)}", True

    environment.update(variables)

    buffer = io.StringIO()
    error_occurred = False
    output = ''

    def custom_print(*args, sep=' ', end='\n', file=None, flush=False):
        if file is None or file == __builtins__.get('stdout'):
            buffer.write(sep.join(map(str, args)) + end)
            print(*args, sep=sep, end=end, file=sys.stdout, flush=flush)
            if flush:
                buffer.flush()
        else:
            __builtins__['print'](*args, sep=sep, end=end, file=file, flush=flush)

    environment['print'] = custom_print

    try:
        code_obj = compile(code, code_filename, 'exec')
        exec(code_obj, environment)
        output = buffer.getvalue()
    except Exception as e:
        output = (
            f"{buffer.getvalue()}\n"
            f"Execution error: {str(e)}\n"
            f"Type: {type(e).__name__}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        error_occurred = True
        output = format_runtime_error(output, method_context)

    return output, error_occurred
