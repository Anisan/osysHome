# -*- coding: utf-8 -*-
"""Отправка аналитики на osysHome.ru."""
from app.analytics.collector import collect_payload, ANALYTICS_URL
from app.core.lib.object import getProperty
from app.logging_config import getLogger

_logger = getLogger("analytics")


def should_send() -> bool:
    """Проверяет, включена ли отправка аналитики."""
    return bool(_get_send_level())


def _get_send_level() -> str:
    """Возвращает уровень отправки: 'basic', 'extended' или ''."""
    v = getProperty("SystemVar.analytics_enabled")
    if v is None:
        return ""
    s = str(v).lower()
    if s in ("basic", "extended"):
        return s
    if s in ("disabled", ""):
        return ""
    if s in ("true", "1", "yes"):
        return "basic"
    return ""


def send_analytics() -> bool:
    """
    Собирает данные и отправляет на osysHome.ru.
    Возвращает True при успехе, False при ошибке или отключённой аналитике.
    """
    level = _get_send_level()
    if not level:
        _logger.debug("Analytics disabled or not opted in, skip send")
        return False
    try:
        import json
        import urllib.request

        payload = collect_payload(level=level)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        _logger.debug("Analytics sending to %s: %s", ANALYTICS_URL, payload)

        req = urllib.request.Request(
            ANALYTICS_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = resp.read().decode("utf-8", errors="replace")
            _logger.debug("Analytics response status=%s body=%s", resp.status, resp_body)
            if 200 <= resp.status < 300:
                _logger.info("Analytics sent successfully to osysHome.ru")
                return True
            _logger.warning("Analytics server returned %s: %s", resp.status, resp_body)
            return False
    except Exception as e:
        _logger.debug("Analytics send failed: %s", e)
        return False
