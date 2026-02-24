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
        '%(asctime)s.%(msecs)03d[%(levelname)s]%(message)s',
        datefmt='%H:%M:%S'
    )
    # Формат для ошибок
    formatter_error = logging.Formatter(
        '%(asctime)s.%(msecs)03d[%(levelname)s][%(name)s]%(message)s',
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

# === Security Audit Logger (несанкционированный доступ) ===
_security_audit_handler = None


def get_security_audit_logger(logDirectory='logs'):
    """Логгер для аудита безопасности: несанкционированный доступ, неудачные логины, 401/403."""
    global _security_audit_handler

    logger = logging.getLogger('security_audit')
    if logger.handlers:
        return logger

    if not os.path.exists(logDirectory):
        os.makedirs(logDirectory)

    log_file = os.path.join(logDirectory, 'security_audit.log')
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d[%(levelname)s]%(message)s',
        datefmt='%H:%M:%S'
    )

    _security_audit_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8',
        utc=False
    )
    _security_audit_handler.setFormatter(formatter)

    # Уровень INFO, чтобы писать как успешные действия (LOGIN_SUCCESS, LOGOUT),
    # так и предупреждения/ошибки безопасности.
    logger.setLevel(logging.INFO)
    logger.addHandler(_security_audit_handler)
    logger.propagate = False
    return logger


def security_audit_log(event_type, ip=None, url='', endpoint='', reason='', username='', user_agent='', **extra):
    """
    Запись события безопасности в security_audit.log.

    Args:
        event_type: UNAUTHORIZED, LOGIN_FAILED, API_KEY_MISSING, API_KEY_INVALID, FORBIDDEN, WS_UNAUTHORIZED
        ip: IP-адрес клиента
        url: URL запроса
        endpoint: endpoint/method
        reason: причина (опционально)
        username: имя пользователя при логине (опционально)
        user_agent: User-Agent (опционально)
        **extra: дополнительные поля
    """
    logger = get_security_audit_logger()
    parts = [f"[{event_type}]", f"IP={ip or '?'}", f"URL={url}", f"Endpoint={endpoint}"]
    if reason:
        parts.append(f"Reason={reason}")
    if username:
        parts.append(f"User={username}")
    if user_agent:
        parts.append(f"UA={user_agent[:80]}")
    for k, v in extra.items():
        if v is not None and v != '':
            parts.append(f"{k}={v}")

    message = " | ".join(str(p) for p in parts)

    # Успешные действия логируем на INFO, подозрительные/ошибки — на WARNING.
    if event_type in ('LOGIN_SUCCESS', 'LOGOUT'):
        logger.info(message)
    else:
        logger.warning(message)
