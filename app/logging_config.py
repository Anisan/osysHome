""" Module init logger """
import logging
import logging.handlers
import os
import sys
import traceback
from app.configuration import Config

# Глобальные handlers (чтобы не дублировались для каждого модуля)
_global_error_handler = None
_shared_app_file_handler = None

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_log_directory():
    return _resolve_log_directory(None)


def _resolve_log_directory(logDirectory=None):
    """Абсолютный путь к каталогу логов из аргумента или Config.LOG_DIRECTORY."""
    if logDirectory is None:
        logDirectory = getattr(Config, 'LOG_DIRECTORY', 'logs') or 'logs'
    if not os.path.isabs(logDirectory):
        return os.path.join(_PROJECT_ROOT, logDirectory)
    return logDirectory


def _resolve_log_level(level=None):
    """Уровень: явный аргумент, иначе DEBUG при Config.DEBUG, иначе LOG_MIN_LEVEL."""
    if level is not None and str(level).upper() != 'NONE':
        return str(level).upper()
    if Config.DEBUG:
        return 'DEBUG'
    return str(getattr(Config, 'LOG_MIN_LEVEL', 'INFO') or 'INFO').upper()


def _backup_count(default=7):
    return int(getattr(Config, 'LOG_BACKUP_COUNT', default) or default)


def _memory_capacity():
    return int(getattr(Config, 'LOG_MEMORY_HANDLER_CAPACITY', 0) or 0)


def _maybe_buffer(target_handler):
    """Оборачивает file handler в MemoryHandler при capacity > 0."""
    capacity = _memory_capacity()
    if capacity <= 0:
        return target_handler
    return logging.handlers.MemoryHandler(
        capacity=capacity,
        flushLevel=logging.ERROR,
        target=target_handler,
    )


def _make_timed_handler(log_file, backup_count, formatter, level=None):
    handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=backup_count,
        encoding='utf-8',
        utc=False,
        delay=True,
    )
    handler.setFormatter(formatter)
    if level is not None:
        handler.setLevel(level)
    return handler


def getLogger(moduleName, level=None, logDirectory=None):
    """ Get logger with file rotation, console output and shared error handler.

    Args:
        moduleName (str): Имя логгера (обычно имя модуля).
        level (str, optional): Уровень логирования. По умолчанию LOG_MIN_LEVEL
            (DEBUG если Config.DEBUG).
        logDirectory (str, optional): Папка для логов. Defaults to Config.LOG_DIRECTORY.

    Returns:
        logging.Logger: настроенный логгер.
    """
    global _global_error_handler, _shared_app_file_handler

    # Если логгер уже настроен — возвращаем как есть
    logger = logging.getLogger(moduleName)
    if logger.handlers:
        return logger

    level = _resolve_log_level(level)
    file_enabled = bool(getattr(Config, 'LOG_FILE_ENABLED', True))
    console_enabled = bool(getattr(Config, 'LOG_CONSOLE_ENABLED', True))
    per_module = bool(getattr(Config, 'LOG_PER_MODULE_FILES', True))
    backup = _backup_count(7)

    # Общий формат для всех выводов
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d[%(levelname)s]%(message)s',
        datefmt='%H:%M:%S'
    )
    # Формат для ошибок / console
    formatter_error = logging.Formatter(
        '%(asctime)s.%(msecs)03d[%(levelname)s][%(name)s]%(message)s',
        datefmt='%H:%M:%S'
    )

    if file_enabled:
        log_dir = _resolve_log_directory(logDirectory)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_errors = os.path.join(log_dir, 'errors.log')

        # Общий error handler (создаётся только один раз)
        if _global_error_handler is None:
            err_file = _make_timed_handler(
                log_errors, backup, formatter_error, level=logging.ERROR
            )
            # errors.log пишем сразу (без MemoryHandler), чтобы не терять ERROR в буфере
            _global_error_handler = err_file

        if per_module:
            log_file = os.path.join(log_dir, f'{moduleName}.log')
            file_handler = _maybe_buffer(
                _make_timed_handler(log_file, backup, formatter)
            )
            logger.addHandler(file_handler)
        else:
            if _shared_app_file_handler is None:
                app_log = os.path.join(log_dir, 'app.log')
                _shared_app_file_handler = _maybe_buffer(
                    _make_timed_handler(app_log, backup, formatter_error)
                )
            logger.addHandler(_shared_app_file_handler)

        logger.addHandler(_global_error_handler)

    if console_enabled:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter_error)
        logger.addHandler(console_handler)

    if not logger.handlers:
        logger.addHandler(logging.NullHandler())

    logger.setLevel(level)
    logger.propagate = False

    return logger

# === Security Audit Logger (несанкционированный доступ) ===
_security_audit_handler = None


def get_security_audit_logger(logDirectory=None):
    """Логгер для аудита безопасности: несанкционированный доступ, неудачные логины, 401/403."""
    global _security_audit_handler

    logger = logging.getLogger('security_audit')
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d[%(levelname)s]%(message)s',
        datefmt='%H:%M:%S'
    )

    file_enabled = bool(getattr(Config, 'LOG_FILE_ENABLED', True))
    if file_enabled:
        log_dir = _resolve_log_directory(logDirectory)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file = os.path.join(log_dir, 'security_audit.log')
        _security_audit_handler = _make_timed_handler(
            log_file, _backup_count(30), formatter
        )
        logger.addHandler(_security_audit_handler)
    else:
        # Без файлов — пишем в console, чтобы не терять audit-события
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

    # Уровень INFO, чтобы писать как успешные действия (LOGIN_SUCCESS, LOGOUT),
    # так и предупреждения/ошибки безопасности.
    logger.setLevel(logging.INFO)
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


# === Application Exception Logger (необработанные ошибки 500) ===
_app_exception_handler = None


def get_app_exception_logger(logDirectory=None):
    """Логгер для необработанных исключений приложения (Internal Server Error)."""
    global _app_exception_handler

    logger = logging.getLogger('app_exceptions')
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d[%(levelname)s]%(message)s',
        datefmt='%H:%M:%S'
    )

    file_enabled = bool(getattr(Config, 'LOG_FILE_ENABLED', True))
    if file_enabled:
        log_dir = _resolve_log_directory(logDirectory)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file = os.path.join(log_dir, '500.log')
        _app_exception_handler = _make_timed_handler(
            log_file, _backup_count(30), formatter
        )
        logger.addHandler(_app_exception_handler)
    else:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

    logger.setLevel(logging.ERROR)
    logger.propagate = False
    return logger


def _should_log_app_exception(exc):
    """Не логируем ожидаемые HTTP-ошибки клиента (4xx)."""
    from werkzeug.exceptions import HTTPException

    if isinstance(exc, HTTPException):
        code = exc.code or 500
        return code >= 500
    return True


def _resolve_exception(exc):
    """Возвращает исходное исключение (Flask 3 оборачивает его в InternalServerError)."""
    original = getattr(exc, 'original_exception', None)
    if original is not None:
        return original
    return exc


def log_app_exception(exc, exc_info=None, **extra):
    """
    Запись необработанного исключения в 500.log с traceback.

    Работает в production и debug; вызывать из Flask error handler.
    """
    exc = _resolve_exception(exc)
    if not _should_log_app_exception(exc):
        return

    try:
        from flask import g, has_request_context

        if has_request_context():
            if getattr(g, '_app_exception_logged', False):
                return
            g._app_exception_logged = True
    except Exception:
        pass

    logger = get_app_exception_logger()
    parts = []

    try:
        from flask import has_request_context, request
        from flask_login import current_user

        if has_request_context():
            ip = '?'
            if request.headers.getlist('X-Forwarded-For'):
                ip = request.headers.getlist('X-Forwarded-For')[0]
            else:
                ip = request.remote_addr or '?'

            parts.extend([
                f"resource={request.full_path.rstrip('?') or request.path or request.url}",
                f"endpoint={request.endpoint or '?'}",
                f"method={request.method}",
                f"source_ip={ip}",
                f"user={getattr(current_user, 'username', '') or 'anonymous'}",
            ])
    except Exception:
        pass

    parts.append(f"error={exc!r}")

    for key, value in extra.items():
        if value is not None and value != '':
            parts.append(f"{key}={value}")

    message = " | ".join(str(p) for p in parts)

    if exc_info is None:
        exc_info = sys.exc_info()
    if exc_info[0] is None:
        exc_info = (type(exc), exc, getattr(exc, '__traceback__', None))

    try:
        if exc_info[0] is not None:
            tb = ''.join(traceback.format_exception(*exc_info))
            logger.error(f"{message}\n{tb}")
        else:
            logger.error(message)
        for handler in logger.handlers:
            handler.flush()
    except Exception as log_err:
        logging.getLogger('flask').error(
            "Failed to write 500.log: %s", log_err, exc_info=True
        )
