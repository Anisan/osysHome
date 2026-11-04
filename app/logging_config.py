""" Module init logger """
from __future__ import annotations

import collections
import hashlib
import logging
import logging.handlers
import os
import re
import sys
import threading
import time
import traceback
from app.configuration import Config

# Глобальные handlers (чтобы не дублировались для каждого модуля)
_global_error_handler = None
_shared_app_file_handler = None
_error_rate_handler = None

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Стабильные поля notify: addNotify бампит count при том же name+description.
# Разные fingerprint (логгер + нормализованный текст) → разные notify.
_ERROR_RATE_NOTIFY_SOURCE = 'osysHome'
_ERROR_RATE_NOTIFY_KIND = 'error_rate'
_ERROR_RATE_MUTE_PROPERTY = 'SystemVar.error_rate_mute'
_ERROR_RATE_NAME_I18N = 'Error growth: {logger}'
_ERROR_RATE_MAX_STREAMS = 64
_ERROR_RATE_DESC_MAX = 255  # Notify.description Column(String(255))
_ERROR_RATE_HEX_RE = re.compile(r'\b[0-9a-fA-F]{8,}\b')
_ERROR_RATE_DIGITS_RE = re.compile(r'\d+')

# Кэш mute_id (sha256 fingerprint). None = ещё не загружали из SystemVar.
_mute_cache_lock = threading.Lock()
_mute_ids_cache: set[str] | None = None


def _normalize_error_message(message: str, max_len: int = 200) -> str:
    """Схлопывает пробелы и переменные числа/id, чтобы одна ошибка не плодила ключи."""
    text = ' '.join((message or '').split())
    text = _ERROR_RATE_HEX_RE.sub('#', text)
    text = _ERROR_RATE_DIGITS_RE.sub('#', text)
    if len(text) > max_len:
        text = text[: max_len - 3] + '...'
    return text or '(empty)'


def _mute_id_from_fingerprint(fingerprint: str) -> str:
    """Короткий стабильный id для хранения mute (не полный текст ошибки)."""
    return hashlib.sha256((fingerprint or '').encode('utf-8')).hexdigest()


def _localized_error_rate_name(logger_name: str) -> str:
    """Имя notify на DEFAULT_LANGUAGE (не язык браузера — стабильный bump)."""
    template = _ERROR_RATE_NAME_I18N
    try:
        from flask import has_app_context

        if has_app_context():
            from app import translate

            lang = getattr(Config, 'DEFAULT_LANGUAGE', 'en') or 'en'
            template = translate(_ERROR_RATE_NAME_I18N, lang=lang) or _ERROR_RATE_NAME_I18N
    except Exception:
        template = _ERROR_RATE_NAME_I18N
    name = template.replace('{logger}', logger_name or 'unknown')
    if len(name) > 255:
        name = name[:252] + '...'
    return name


def _read_mute_dict() -> dict:
    """Читает SystemVar.error_rate_mute как dict."""
    try:
        from app.core.lib.object import getProperty

        raw = getProperty(_ERROR_RATE_MUTE_PROPERTY)
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, str) and raw.strip():
            import json

            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    return {}


def _write_mute_dict(data: dict) -> None:
    from app.core.lib.object import setProperty

    setProperty(_ERROR_RATE_MUTE_PROPERTY, data if isinstance(data, dict) else {}, 'osysHome')


def reload_error_rate_mute_cache() -> set[str]:
    """Перечитывает mute_id из SystemVar в in-memory set."""
    global _mute_ids_cache
    ids = {str(k) for k in _read_mute_dict().keys() if k}
    with _mute_cache_lock:
        _mute_ids_cache = ids
    return set(ids)


def _ensure_mute_cache() -> set[str]:
    with _mute_cache_lock:
        cached = _mute_ids_cache
    if cached is not None:
        return cached
    return reload_error_rate_mute_cache()


def is_error_rate_muted(mute_id: str) -> bool:
    if not mute_id:
        return False
    return mute_id in _ensure_mute_cache()


def list_error_rate_mutes() -> list[dict]:
    """Список mute для UI: mute_id, logger, message, created."""
    items = []
    data = _read_mute_dict()
    for mute_id, meta in data.items():
        if not isinstance(meta, dict):
            meta = {}
        items.append(
            {
                'mute_id': str(mute_id),
                'logger': meta.get('logger') or '',
                'message': meta.get('message') or '',
                'created': meta.get('created') or '',
            }
        )
    items.sort(key=lambda row: row.get('created') or '', reverse=True)
    return items


def mute_error_rate(mute_id: str, logger_name: str = '', message: str = '') -> bool:
    """Добавляет mute_id в SystemVar.error_rate_mute и обновляет кэш."""
    mute_id = (mute_id or '').strip()
    if not mute_id:
        return False
    from app.database import get_now_to_utc

    data = _read_mute_dict()
    data[mute_id] = {
        'logger': logger_name or '',
        'message': (message or '')[:_ERROR_RATE_DESC_MAX],
        'created': get_now_to_utc().isoformat(timespec='seconds'),
    }
    _write_mute_dict(data)
    reload_error_rate_mute_cache()
    return True


def unmute_error_rate(mute_id: str) -> bool:
    """Удаляет mute_id из свойства и обновляет кэш."""
    mute_id = (mute_id or '').strip()
    if not mute_id:
        return False
    data = _read_mute_dict()
    if mute_id not in data:
        reload_error_rate_mute_cache()
        return False
    data.pop(mute_id, None)
    _write_mute_dict(data)
    reload_error_rate_mute_cache()
    return True


class ErrorRateNotifyHandler(logging.Handler):
    """Считает ERROR+ по fingerprint (логгер + содержимое) за скользящее окно.

    Разные тексты/модули — независимые счётчики и notify: непрочитанный алерт
    по одной ошибке не блокирует фиксацию другой.
    Пока notify этой ошибки непрочитан — bump count не чаще cooldown_sec.
    После read — снова полный notify при новом наборе порога.
    Mute по mute_id (sha256 fingerprint) suppress только notify.
    """

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self._lock = threading.Lock()
        # fingerprint -> deque[monotonic timestamps]
        self._streams: dict[str, collections.deque[float]] = {}
        # fingerprint -> last addNotify monotonic
        self._last_notify_mono: dict[str, float] = {}
        self._tls = threading.local()

    def _settings(self):
        enabled = bool(getattr(Config, 'LOG_ERROR_RATE_NOTIFY_ENABLED', True))
        window = float(getattr(Config, 'LOG_ERROR_RATE_WINDOW_SEC', 300) or 300)
        threshold = int(getattr(Config, 'LOG_ERROR_RATE_THRESHOLD', 5) or 5)
        cooldown = float(getattr(Config, 'LOG_ERROR_RATE_COOLDOWN_SEC', 600) or 600)
        return enabled, max(1.0, window), max(1, threshold), max(0.0, cooldown)

    @staticmethod
    def _fingerprint(record: logging.LogRecord) -> tuple[str, str, str, str]:
        """Возвращает (key, mute_id, notify_name, notify_description)."""
        logger_name = record.name or 'unknown'
        normalized = _normalize_error_message(record.getMessage())
        key = f'{logger_name}\0{normalized}'
        mute_id = _mute_id_from_fingerprint(key)
        name = _localized_error_rate_name(logger_name)
        description = normalized[:_ERROR_RATE_DESC_MAX]
        return key, mute_id, name, description

    @staticmethod
    def _has_unread_notify(name: str, description: str) -> bool:
        """Непрочитанный notify именно этой ошибки (name+description)."""
        try:
            from app.database import session_scope
            from app.core.models.Plugins import Notify

            with session_scope() as session:
                row = (
                    session.query(Notify.id)
                    .filter(
                        Notify.name == name,
                        Notify.description == description,
                        Notify.source == _ERROR_RATE_NOTIFY_SOURCE,
                        Notify.read == False,  # noqa: E712
                    )
                    .first()
                )
                return row is not None
        except Exception:
            return False

    def _prune_streams_unlocked(self, now: float, window_sec: float) -> None:
        """Удаляет пустые окна и лишние fingerprint (LRU по последней активности)."""
        stale = []
        for key, stamps in self._streams.items():
            cutoff = now - window_sec
            while stamps and stamps[0] < cutoff:
                stamps.popleft()
            if not stamps:
                stale.append(key)
        for key in stale:
            self._streams.pop(key, None)
            self._last_notify_mono.pop(key, None)

        if len(self._streams) <= _ERROR_RATE_MAX_STREAMS:
            return
        # Вытесняем самые давно неактивные
        ranked = sorted(
            self._streams.items(),
            key=lambda item: item[1][-1] if item[1] else 0.0,
        )
        overflow = len(self._streams) - _ERROR_RATE_MAX_STREAMS
        for key, _ in ranked[:overflow]:
            self._streams.pop(key, None)
            self._last_notify_mono.pop(key, None)

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.ERROR:
            return
        if getattr(self._tls, 'notifying', False):
            return

        enabled, window_sec, threshold, cooldown_sec = self._settings()
        if not enabled:
            return

        key, mute_id, notify_name, notify_description = self._fingerprint(record)
        try:
            if is_error_rate_muted(mute_id):
                return
        except Exception:
            pass

        now = time.monotonic()
        count = 0
        with self._lock:
            stamps = self._streams.get(key)
            if stamps is None:
                stamps = collections.deque()
                self._streams[key] = stamps
            stamps.append(now)
            cutoff = now - window_sec
            while stamps and stamps[0] < cutoff:
                stamps.popleft()
            count = len(stamps)
            self._prune_streams_unlocked(now, window_sec)

        if count < threshold:
            return

        unread = self._has_unread_notify(notify_name, notify_description)
        with self._lock:
            last = self._last_notify_mono.get(key, 0.0)
            since_last = now - last
            if unread:
                # Непрочитано: bump не чаще cooldown_sec
                if since_last < cooldown_sec:
                    return
            # После read — новый алерт сразу (без паузы); гонки потоков
            # схлопнутся в bump через одинаковые name+description в addNotify
            self._last_notify_mono[key] = now
            if not unread:
                # Новый алерт по этому fingerprint — окно сбрасываем
                self._streams[key] = collections.deque()

        self._tls.notifying = True
        try:
            from app.core.lib.common import addNotify
            from app.core.lib.constants import CategoryNotify

            addNotify(
                name=notify_name,
                description=notify_description,
                category=CategoryNotify.Warning,
                source=_ERROR_RATE_NOTIFY_SOURCE,
                params={
                    'kind': _ERROR_RATE_NOTIFY_KIND,
                    'mute_id': mute_id,
                    'count': count,
                    'window_sec': int(window_sec),
                    'threshold': threshold,
                    'logger': record.name,
                    'level': record.levelname,
                },
            )
        except Exception:
            # Не логируем здесь — риск рекурсии через тот же handler
            pass
        finally:
            self._tls.notifying = False


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
    global _global_error_handler, _shared_app_file_handler, _error_rate_handler

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

    # Мониторинг роста ERROR → addNotify (независимо от file_enabled)
    if _error_rate_handler is None:
        _error_rate_handler = ErrorRateNotifyHandler()
    logger.addHandler(_error_rate_handler)

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
