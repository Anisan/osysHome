import sys
import io
import traceback

module_names = [
    "app.core.lib.common",
    "app.core.lib.object",
    "app.core.lib.cache",
]

def execute_and_capture_output(code: str, variables: dict) -> (str, bool):
    """Execute code with variables

    Args:
        code (str): Python code
        variables (dict): Dictionary variables

    Returns:
        str: Output
        bool: Error execute
        
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
    
    # Захватываем стандартный вывод
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    error = False
    try:
        # Выполняем пользовательский код в окружении
        exec(code, environment)
        # Получаем результат из захваченного вывода
        output = sys.stdout.getvalue()
    except Exception as e:
        output =  f"Exception: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        error = True
    finally:
        # Восстанавливаем стандартный вывод
        sys.stdout = old_stdout
    
    return output, error