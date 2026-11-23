"""Оркестратор диагностики ядра: read_only и sandbox probe."""

from __future__ import annotations

import time
from typing import Any, Literal, Optional

from app.core.diagnostics.probes import (
    SANDBOX_OBJECT_PREFIX,
    probe_batch_writer_stats,
    probe_database,
    probe_history_roundtrip,
    probe_method_invoke,
    probe_objects_storage,
    probe_property_roundtrip,
    probe_thread_pools,
)
from app.logging_config import getLogger

_logger = getLogger("diagnostics")

SANDBOX_OBJECT_NAME = "__CoreProbe"
SANDBOX_PROPERTY_NAME = "probe"
SANDBOX_HISTORY_PROPERTY_NAME = "probe_hist"
SANDBOX_METHOD_NAME = "ping"
SANDBOX_CLASS_NAME = "__CoreProbeClass"

Mode = Literal["read_only", "probe"]


def _ensure_sandbox_object(
    object_name: str = SANDBOX_OBJECT_NAME,
    *,
    cleanup_links: bool = True,
) -> dict:
    """Создать/подготовить sandbox-объект без внешних links."""
    from app.core.lib.constants import PropertyType
    from app.core.lib.object import (
        addClass,
        addObject,
        addObjectMethod,
        addObjectProperty,
        getObject,
    )

    if not object_name.startswith(SANDBOX_OBJECT_PREFIX):
        raise PermissionError(
            f"Sandbox object must start with {SANDBOX_OBJECT_PREFIX!r}"
        )

    addClass(
        SANDBOX_CLASS_NAME,
        description="Internal diagnostics sandbox class",
        update=True,
    )
    addObject(
        object_name,
        class_name=SANDBOX_CLASS_NAME,
        description="Internal diagnostics sandbox object",
        update=True,
    )
    addObjectProperty(
        SANDBOX_PROPERTY_NAME,
        object_name,
        description="Diagnostics probe property (no history)",
        type=PropertyType.String,
        history=0,
        update=True,
    )
    # Свойство с историей — для пробы записи History в БД пользователя
    addObjectProperty(
        SANDBOX_HISTORY_PROPERTY_NAME,
        object_name,
        description="Diagnostics history probe property",
        type=PropertyType.String,
        history=1,
        update=True,
    )
    addObjectMethod(
        SANDBOX_METHOD_NAME,
        object_name,
        description="Diagnostics ping method",
        code="return 'pong'",
        update=True,
    )

    obj = getObject(object_name)
    if obj is None:
        raise RuntimeError(f"Failed to load sandbox object {object_name}")

    from app.core.diagnostics.probes import _object_has_external_links

    links = _object_has_external_links(obj)
    if links:
        raise RuntimeError(
            "Sandbox object has external links (refuse probe): " + ", ".join(links[:10])
        )

    return {
        "object": object_name,
        "property": SANDBOX_PROPERTY_NAME,
        "history_property": SANDBOX_HISTORY_PROPERTY_NAME,
        "method": SANDBOX_METHOD_NAME,
        "cleanup_links": cleanup_links,
    }


def _cleanup_sandbox_object(object_name: str, *, delete: bool = False) -> None:
    """Опциональная очистка sandbox-объекта после probe."""
    if not delete:
        return
    try:
        from app.core.lib.object import deleteObject

        deleteObject(object_name)
    except Exception as ex:
        _logger.warning("sandbox cleanup failed for %s: %s", object_name, ex)


def run_core_diagnostics(
    mode: Mode = "read_only",
    *,
    sandbox_object: str = SANDBOX_OBJECT_NAME,
    probe_iterations: int = 5,
    history_iterations: int = 3,
    include_history: bool = True,
    cleanup_history_rows: bool = True,
    delete_sandbox: bool = False,
    include_plugins_hint: bool = False,
) -> dict[str, Any]:
    """Запуск диагностики ядра.

    Args:
        mode: ``read_only`` — только безопасные проверки настроенной БД;
            ``probe`` — + write/read/method/history на sandbox ``__CoreProbe*``.
        sandbox_object: имя sandbox-объекта (должен начинаться с ``__CoreProbe``).
        probe_iterations: число итераций property roundtrip без истории.
        history_iterations: число записей истории в БД пользователя.
        include_history: в probe-режиме проверять запись History в настроенную БД.
        cleanup_history_rows: удалить строки History, созданные этой пробой.
        delete_sandbox: удалить sandbox после probe (по умолчанию оставить).
        include_plugins_hint: добавить в отчёт подсказку про MCP plugin smoke.

    Returns:
        dict: ``{all_ok, mode, checks, metrics, elapsed_ms, warnings}``
    """
    started = time.perf_counter()
    checks: list[dict] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}

    if mode not in ("read_only", "probe"):
        return {
            "all_ok": False,
            "mode": mode,
            "checks": [{"name": "mode", "ok": False, "error": f"Unknown mode: {mode}"}],
            "metrics": {},
            "warnings": [],
            "elapsed_ms": 0.0,
        }

    checks.append(probe_database())
    checks.append(probe_objects_storage())
    checks.append(probe_thread_pools())
    checks.append(probe_batch_writer_stats())

    for item in checks:
        if item.get("warning"):
            warnings.append(f"{item['name']}: {item['warning']}")
        detail = item.get("detail") or {}
        if item["name"] == "database":
            metrics["db_ms"] = item.get("ms")
            metrics["database"] = {
                "dialect": detail.get("dialect"),
                "uri_masked": detail.get("uri_masked"),
                "values_table": detail.get("values_table"),
                "history_table": detail.get("history_table"),
                "pool_size": detail.get("pool_size"),
            }
        elif item["name"] == "objects_storage":
            metrics["objects_loaded"] = detail.get("objects_loaded")
            metrics["avg_get_object_ms"] = detail.get("avg_get_object_ms")
        elif item["name"] == "thread_pools":
            metrics["pools"] = detail.get("pools")
        elif item["name"] == "batch_writer":
            metrics["batch_writer"] = detail

    sandbox_meta: Optional[dict] = None
    if mode == "probe":
        try:
            sandbox_meta = _ensure_sandbox_object(sandbox_object)
            checks.append(
                probe_property_roundtrip(
                    sandbox_object,
                    SANDBOX_PROPERTY_NAME,
                    iterations=probe_iterations,
                    save_history=False,
                    flush_batch=True,
                )
            )
            checks.append(probe_method_invoke(sandbox_object, SANDBOX_METHOD_NAME))
            if include_history:
                checks.append(
                    probe_history_roundtrip(
                        sandbox_object,
                        SANDBOX_HISTORY_PROPERTY_NAME,
                        iterations=history_iterations,
                        cleanup_rows=cleanup_history_rows,
                    )
                )
        except Exception as ex:
            _logger.exception("probe mode setup/run failed")
            checks.append({"name": "probe_setup", "ok": False, "error": str(ex), "ms": 0.0})
        finally:
            if delete_sandbox:
                _cleanup_sandbox_object(sandbox_object, delete=True)

        for item in checks:
            if item.get("name") == "property_roundtrip" and item.get("ok"):
                metrics["property_roundtrip_ms"] = (item.get("detail") or {}).get("latency_ms")
                metrics["property_flush_ms"] = (item.get("detail") or {}).get("flush_latency_ms")
            if item.get("name") == "method_invoke" and item.get("ok"):
                metrics["method_invoke_ms"] = item.get("ms")
            if item.get("name") == "history_roundtrip" and item.get("ok"):
                detail = item.get("detail") or {}
                metrics["history_roundtrip_ms"] = detail.get("latency_ms")
                metrics["history_flush_ms"] = detail.get("flush_latency_ms")
                metrics["history_rows_inserted"] = detail.get("history_rows_inserted")

    if include_plugins_hint:
        metrics["plugins_hint"] = (
            "Проверку MCP-плагинов выполняйте через osys_self_test / plugin capabilities; "
            "отсутствие плагина в whitelist не должно валить ядро."
        )

    all_ok = all(bool(item.get("ok")) for item in checks)
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return {
        "all_ok": all_ok,
        "mode": mode,
        "checks": checks,
        "metrics": metrics,
        "warnings": warnings,
        "elapsed_ms": elapsed_ms,
        "sandbox": sandbox_meta,
    }
