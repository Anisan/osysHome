"""Runtime helpers for executing method / CustomFunction Python code."""
import ast
import io
import re
import sys
import threading
import traceback
from types import CodeType
from typing import Any, Dict, List, Optional, Tuple

_METHOD_WRAPPER_NAME = "__osys_method_exec__"

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
    """Drop the merged runtime environment cache.

    Base module imports stay cached; only CustomFunction bindings are cleared.
    """
    global _runtime_environment, _runtime_cf_revision
    with _env_lock:
        _runtime_environment = None
        _runtime_cf_revision = -1


def _build_base_module_environment() -> Dict[str, Any]:
    """Build an execution environment with standard module imports only."""
    environment = globals().copy()
    for module_name in MODULE_NAMES:
        import_statement = f'from {module_name} import *'
        exec(import_statement, environment)
    return environment


def get_base_module_environment() -> Dict[str, Any]:
    """Return a copy of the cached base import environment.

    Used for CustomFunction compile/validate (no CustomFunction bindings).

    Returns:
        dict: Shallow copy of the base environment
    """
    global _base_environment
    with _env_lock:
        if _base_environment is None:
            _base_environment = _build_base_module_environment()
        return dict(_base_environment)


def build_module_environment() -> Dict[str, Any]:
    """Backward-compatible alias for :func:`get_base_module_environment`.

    Returns:
        dict: Base imports only (no CustomFunction bindings)
    """
    return get_base_module_environment()


def _get_runtime_environment() -> Dict[str, Any]:
    """Return cached base environment merged with CustomFunction bindings."""
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
    """Prepend human-readable CustomFunction / method context to error output.

    Args:
        output (str): Captured traceback / error text
        method_context (dict, optional): Keys such as ``object``, ``method``,
            ``owner``, ``source``

    Returns:
        str: Formatted error text (or original ``output`` if nothing to add)
    """
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


def _body_has_toplevel_return(body: List[ast.stmt]) -> bool:
    """True if *body* contains ``return`` outside nested def/class scopes."""
    for node in body:
        if isinstance(node, ast.Return):
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for attr in ("body", "orelse", "finalbody"):
            child = getattr(node, attr, None)
            if isinstance(child, list) and _body_has_toplevel_return(child):
                return True
        handlers = getattr(node, "handlers", None)
        if isinstance(handlers, list):
            for handler in handlers:
                if _body_has_toplevel_return(handler.body):
                    return True
        cases = getattr(node, "cases", None)
        if isinstance(cases, list):
            for case in cases:
                if _body_has_toplevel_return(case.body):
                    return True
    return False


def compile_method_code(code: str, filename: str = "<string>") -> CodeType:
    """Compile method/task code for ``exec``, allowing top-level ``return``.

    When the AST has a ``return`` outside ``def``/``class``, the module body is
    wrapped in a synthetic function and call via AST (not text indent) so
    original line numbers stay intact for tracebacks. Code without top-level
    ``return`` compiles unchanged.
    """
    tree = ast.parse(code or "", filename=filename, mode="exec")
    if _body_has_toplevel_return(tree.body):
        wrapper = ast.FunctionDef(
            name=_METHOD_WRAPPER_NAME,
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=list(tree.body) if tree.body else [ast.Pass()],
            decorator_list=[],
            returns=None,
            type_params=[],
        )
        call = ast.Expr(
            value=ast.Call(
                func=ast.Name(id=_METHOD_WRAPPER_NAME, ctx=ast.Load()),
                args=[],
                keywords=[],
            )
        )
        tree.body = [wrapper, call]
        ast.fix_missing_locations(tree)
    return compile(tree, filename, "exec")


def execute_and_capture_output(
    code: str,
    variables: dict,
    code_filename: str = '<string>',
    method_context: Optional[dict] = None,
) -> Tuple[str, bool]:
    """Execute Python code with provided variables and capture output/errors.

    Args:
        code (str): Python source to run
        variables (dict): Locals/globals overlay (``self``, ``params``, etc.)
        code_filename (str, optional): Virtual filename for compile/traceback.
            Defaults to ``'<string>'``.
        method_context (dict, optional): Passed to
            :func:`format_runtime_error` on failure

    Returns:
        tuple[str, bool]: Captured output (possibly formatted) and error flag
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
        code_obj = compile_method_code(code, code_filename)
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
