""" Module init logger """
import logging
import logging.handlers
import os
from app.configuration import Config

# Глобальный error handler (чтобы не дублировался для каждого модуля)
_global_error_handler = None


def getLogger(moduleName, level=None, logDirectory='logs'):
    """ Get logger with file rotation, console output and shared error handler.

    Args:
        moduleName (str): Имя логгера (обычно имя модуля).
        level (str, optional): Уровень логирования. По умолчанию INFO (DEBUG если Config.DEBUG).
        logDirectory (str, optional): Папка для логов. Defaults to 'logs'.

    Returns:
        logging.Logger: настроенный логгер.
    """
    global _global_error_handler

    # Если логгер уже настроен — возвращаем как есть
    logger = logging.getLogger(moduleName)
    if logger.handlers:
        return logger

    # Создаём папку логов при необходимости
    if not os.path.exists(logDirectory):
        os.makedirs(logDirectory)

    # Определяем уровень логирования
    if level is None or str(level).upper() == 'NONE':
        level = 'DEBUG' if Config.DEBUG else 'INFO'
    else:
        level = level.upper()

    logFile = os.path.join(logDirectory, f'{moduleName}.log')
    logErrors = os.path.join(logDirectory, 'errors.log')

    # Общий формат для всех выводов
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d[%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    # Формат для ошибок
    formatter_error = logging.Formatter(
        '%(asctime)s.%(msecs)03d[%(levelname)s][%(name)s] %(message)s',
        datefmt='%H:%M:%S'
    )

    # Индивидуальный file handler для модуля
    file_handler = logging.handlers.TimedRotatingFileHandler(
        logFile,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8',
        utc=False
    )
    file_handler.setFormatter(formatter)

    # Общий error handler (создаётся только один раз)
    if _global_error_handler is None:
        _global_error_handler = logging.handlers.TimedRotatingFileHandler(
            logErrors,
            when='midnight',
            interval=1,
            backupCount=7,
            encoding='utf-8',
            utc=False
        )
        _global_error_handler.setLevel(logging.ERROR)
        _global_error_handler.setFormatter(formatter_error)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter_error)

    # Настраиваем логгер
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(_global_error_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger

# Пример использования в модуле: 
# logger = getLogger('module1')
