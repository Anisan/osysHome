""" Module init logger """
import logging
import logging.config
import logging.handlers
import os
from settings import Config

def getLogger(moduleName, level=None, logDirectory='logs'):
    """ Get logger

    Args:
        moduleName (String): Name logger
        level (String): Level logger.
        logDirectory (str, optional): directory for logs. Defaults to 'logs'.

    Returns:
        logger: logger
    """
    if level is None:
        level = 'INFO'

        if Config.DEBUG:
            level = 'DEBUG'

    if not os.path.exists(logDirectory):
        os.makedirs(logDirectory)

    logFile = os.path.join(logDirectory, f'{moduleName}.log')

    loggingConfig = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s[%(levelname)s] %(message)s',
                'datefmt': '%H:%M:%S'
            },
            'console_formatter': {
                'format': '%(asctime)s[%(levelname)s] %(name)s: %(message)s',
                'datefmt': '%H:%M:%S'
            },
        },
        'handlers': {
            f'{moduleName}_file_handler': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'formatter': 'standard',
                'filename': logFile,
                'when': 'midnight',
                'interval': 1,
                'backupCount': 7,  # Хранить последние 7 файлов логов
                'encoding': 'utf-8',
                'utc': False  # Использовать локальное время
            },
            f'{moduleName}_console_handler': {
                'class': 'logging.StreamHandler',
                'formatter': 'console_formatter',
                'level': level
            },
        },
        'loggers': {
            moduleName: {
                'handlers': [f'{moduleName}_file_handler', f'{moduleName}_console_handler'],
                'level': level,
                'propagate': False
            },
        }
    }

    logging.config.dictConfig(loggingConfig)
    return logging.getLogger(moduleName)

# Пример использования в модуле:
# logger = getLogger('module1')
