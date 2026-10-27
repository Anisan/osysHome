"""Корректное завершение: сброс BatchWriter, логов, onStop, плагинов.

Нужен при systemctl stop/restart и перед os._exit в restart_system —
иначе при увеличенном batch_writer_flush_interval теряются значения/history.
"""
from __future__ import annotations

import atexit
import logging
import signal
import sys
import threading

_lock = threading.Lock()
_done = False
_flask_app = None


def set_flask_app(app) -> None:
    """Сохраняет Flask app для app_context при lifecycle onStop."""
    global _flask_app
    _flask_app = app


def flush_logging_handlers() -> None:
    """Сбрасывает MemoryHandler и остальные handlers всех логгеров."""
    loggers = [logging.getLogger()]
    loggers.extend(
        logging.getLogger(name)
        for name in list(logging.Logger.manager.loggerDict.keys())
    )
    for logger in loggers:
        for handler in list(getattr(logger, 'handlers', []) or []):
            try:
                if hasattr(handler, 'flush'):
                    handler.flush()
                # MemoryHandler: target тоже сбросить
                target = getattr(handler, 'target', None)
                if target is not None and hasattr(target, 'flush'):
                    target.flush()
            except Exception:
                pass


def graceful_shutdown(reason: str = '') -> None:
    """Однократный сброс данных и остановка фоновых частей ядра."""
    global _done
    with _lock:
        if _done:
            return
        _done = True

    msg = f"Graceful shutdown ({reason})" if reason else "Graceful shutdown"
    try:
        logging.getLogger('main').info(msg)
    except Exception:
        print(msg, file=sys.stderr)

    try:
        from app.core.main.ObjectManager import shutdown_batch_writer
        shutdown_batch_writer()
    except Exception as ex:
        try:
            logging.getLogger('main').exception("BatchWriter shutdown failed: %s", ex)
        except Exception:
            print(f"BatchWriter shutdown failed: {ex}", file=sys.stderr)

    try:
        from app.core.lib.common import (
            flushBufferedCoreSystemStatsMetrics,
            flushSystemStatsWsNotifications,
        )
        flushBufferedCoreSystemStatsMetrics()
        flushSystemStatsWsNotifications()
    except Exception:
        pass

    flush_logging_handlers()

    app = _flask_app
    if app is not None:
        try:
            from app.core.main.ObjectsStorage import objects_storage
            with app.app_context():
                objects_storage.stop_background_preload()
                objects_storage.invoke_lifecycle_all("onStop")
        except Exception as ex:
            try:
                logging.getLogger('main').exception("onStop failed: %s", ex)
            except Exception:
                pass

    try:
        from app.core.main.PluginsHelper import stop_plugins
        stop_plugins()
    except Exception as ex:
        try:
            logging.getLogger('main').exception("stop_plugins failed: %s", ex)
        except Exception:
            pass

    flush_logging_handlers()


def _signal_handler(signum, frame):
    name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    graceful_shutdown(f"signal {name}")
    # Даём главному циклу завершиться; при повторном сигнале — жёсткий выход
    sys.exit(0)


def register_shutdown_handlers(app=None) -> None:
    """Регистрирует atexit и SIGTERM/SIGINT (idempotent по процессу)."""
    if app is not None:
        set_flask_app(app)

    atexit.register(lambda: graceful_shutdown('atexit'))

    if hasattr(signal, 'SIGTERM'):
        try:
            signal.signal(signal.SIGTERM, _signal_handler)
        except (ValueError, OSError):
            # Не главный поток / платформа не поддерживает
            pass
    if hasattr(signal, 'SIGINT'):
        try:
            signal.signal(signal.SIGINT, _signal_handler)
        except (ValueError, OSError):
            pass
