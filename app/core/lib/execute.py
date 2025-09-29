import io
import sys
import traceback
from typing import Tuple

MODULE_NAMES = [
    "app.core.lib.common",
    "app.core.lib.constants",
    "app.core.lib.object",
    "app.core.lib.cache",
    "app.core.lib.sql",
]

def execute_and_capture_output(code: str, variables: dict) -> Tuple[str, bool]:
    """Execute Python code with provided variables and capture output/errors via custom print.

    Executes the given code in a custom environment that includes:
    - Pre-imported specified modules
    - Provided variables

    Args:
        code (str): Python code to execute. If empty or None, returns empty output.
        variables (dict): Dictionary of variables to include in the execution environment.

    Returns:
        str: Captured stdout output or error message
        bool: True if execution resulted in error, False otherwise
    """
    # Early return for empty code
    if not code:
        return "", False

    # Создаем окружение и добавляем в него переменные
    environment = globals().copy()
    environment.update(variables)

    # Выполняем импорт для каждого модуля в окружении
    for module_name in MODULE_NAMES:
        try:
            import_statement = f'from {module_name} import *'
            exec(import_statement, environment)
        except Exception as e:
            return f"Failed to import {module_name}: {str(e)}", True

    buffer = io.StringIO()
    error_occurred = False
    output = ''

    # Переопределяем print в окружении
    def custom_print(*args, sep=' ', end='\n', file=None, flush=False):
        if file is None or file == __builtins__.get('stdout'):
            buffer.write(sep.join(map(str, args)) + end)
            print(*args, sep=sep, end=end, file=sys.stdout, flush=flush)
            if flush:
                buffer.flush()
        else:
            __builtins__['print'](*args, sep=sep, end=end, file=file, flush=flush)

    # Заменяем print в окружении
    environment['print'] = custom_print

    try:
        exec(code, environment)
        output = buffer.getvalue()
    except Exception as e:
        output = (
            f"{buffer.getvalue()}\n"
            f"Execution error: {str(e)}\n"
            f"Type: {type(e).__name__}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        error_occurred = True

    return output, error_occurred