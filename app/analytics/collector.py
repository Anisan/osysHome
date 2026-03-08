# -*- coding: utf-8 -*-
"""Сбор данных для аналитики (по аналогии с Home Assistant).

basic: uuid, version, os, core_branch, installation_type
extended: basic + integrations, object_count, user_count,
          class_count, property_count, method_count, history_count
"""
import os
import platform
from app.core.lib.object import getProperty, getObjectsByClass
from app.core.main.PluginsHelper import plugins
from app.utils import get_current_version


# WordPress REST API endpoint (mu-plugin must be installed on osysHome.ru)
ANALYTICS_URL = "https://osysHome.ru/wp-json/osyshome/v1/analytics"


def _detect_os() -> str:
    """Определение операционной системы."""
    return platform.system() or "unknown"


def _detect_installation_type() -> str:
    """Определение типа установки."""
    if os.path.exists("/.dockerenv"):
        return "Docker"
    if os.environ.get("VIRTUAL_ENV"):
        return "venv"
    if os.environ.get("CONDA_DEFAULT_ENV"):
        return "conda"
    if platform.system() == "Windows":
        return "Windows"
    return "pip"


def _ensure_uuid() -> str:
    """Возвращает UUID установки (генерируется при initSystemVar, readonly)."""
    uid = getProperty("SystemVar.analytics_uuid")
    return uid or ""


def collect_payload(level: str = "basic") -> dict:
    """Собирает payload. level: 'basic' | 'extended'."""
    uuid_val = _ensure_uuid()
    if not uuid_val or len(uuid_val) < 10:
        raise ValueError("analytics_uuid not set or invalid")

    payload = {
        "uuid": uuid_val,
        "version": get_current_version(),
        "os": _detect_os(),
        "core_branch": str(getProperty("SystemVar.core_branch") or ""),
        "installation_type": _detect_installation_type(),
    }

    if level != "extended":
        return payload

    # extended
    integrations = []
    for name, mod in plugins.items():
        try:
            v = getattr(mod.get("instance"), "version", None) or ""
            integrations.append(f"{name}@{v}" if v else name)
        except Exception:
            integrations.append(name)

    users = getObjectsByClass("Users")
    user_count = len(users) if users else 0

    from app.core.models.Clasess import Object, Class, Property, Method, History
    from app.database import session_scope
    with session_scope() as session:
        object_count = session.query(Object).count()
        class_count = session.query(Class).count()
        property_count = session.query(Property).count()
        method_count = session.query(Method).count()
        history_count = session.query(History).count()

    payload.update({
        "integrations": integrations,
        "integration_count": len(integrations),
        "object_count": object_count,
        "user_count": user_count,
        "class_count": class_count,
        "property_count": property_count,
        "method_count": method_count,
        "history_count": history_count,
    })
    return payload
