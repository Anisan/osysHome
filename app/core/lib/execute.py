import sys
import io
import traceback
from contextlib import redirect_stdout

module_names = [
    "app.core.lib.common",
    "app.core.lib.constants",
    "app.core.lib.object",
    "app.core.lib.cache",
    "app.core.lib.sql",
]


def execute_and_capture_output(code: str, variables: dict):
    """Execute code with variables and capture output.

    Args:
        code (str): Python code to execute.
        variables (dict): Dictionary of variables to include in the execution environment.

    Returns:
        str: Captured output or error message.
        bool: True if an error occurred, False otherwise.
    """
    if code is None or code == '':
        return '', False
    # Создаем окружение и добавляем в него переменные
    environment = globals().copy()
    environment.update(variables)

    # Выполняем импорт для каждого модуля в окружении
    for module_name in module_names:
        import_statement = f'from {module_name} import *'
        exec(import_statement, environment)

    buffer = io.StringIO()
    error = False
    output = ''
    
    with redirect_stdout(buffer):
        try:
            exec(code, environment, locals())
            output = buffer.getvalue()  # Читаем данные до закрытия
        except Exception as e:
            output = f"Exception: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            error = True

    return output, error
