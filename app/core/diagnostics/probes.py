"""Зонды диагностики ядра (БД, storage, пулы, BatchWriter, sandbox write)."""

from __future__ import annotations

import statistics
import time
from typing import Any, Callable, Optional

from sqlalchemy import text

from app.database import session_scope
from app.logging_config import getLogger

_logger = getLogger("diagnostics")

SANDBOX_OBJECT_PREFIX = "__CoreProbe"


def _timed(fn: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    result = fn()
    return result, (time.perf_counter() - started) * 1000.0


def _ok(name: str, *, ms: float = 0.0, detail: Optional[dict] = None, warning: Optional[str] = None) -> dict:
    item = {"name": name, "ok": True, "ms": round(ms, 3)}
    if detail is not None:
        item["detail"] = detail
    if warning:
        item["warning"] = warning
    return item


def _fail(name: str, error: str, *, ms: float = 0.0) -> dict:
    return {"name": name, "ok": False, "ms": round(ms, 3), "error": str(error)}


def _mask_db_uri(uri: str) -> str:
    """Скрыть пароль в SQLAlchemy URI для отчёта."""
    if not uri:
        return ""
    try:
        # dialect+driver://user:password@host/db → user:***@host/db
        if "://" not in uri:
            return uri
        scheme, rest = uri.split("://", 1)
        if "@" in rest and ":" in rest.split("@", 1)[0]:
            creds, hostpart = rest.split("@", 1)
            user = creds.split(":", 1)[0]
            return f"{scheme}://{user}:***@{hostpart}"
        return uri
    except Exception:
        return "<masked>"


def _db_connection_info() -> dict:
    from app.configuration import Config

    uri = str(getattr(Config, "SQLALCHEMY_DATABASE_URI", "") or "")
    dialect = uri.split(":", 1)[0] if uri else "unknown"
    return {
        "dialect": dialect,
        "uri_masked": _mask_db_uri(uri),
        "pool_size": getattr(Config, "SQLALCHEMY_POOL_SIZE", None),
    }


def probe_database() -> dict:
    """Проверка доступности настроенной БД пользователя: SELECT 1 + метаданные URI."""
    info = _db_connection_info()
    try:
        def _run():
            from app.core.models.Clasess import History, Value

            with session_scope() as session:
                session.execute(text("SELECT 1"))
                # Лёгкое чтение таблиц приложения в БД пользователя
                try:
                    session.query(Value.id).limit(1).all()
                    info["values_table"] = "ok"
                except Exception as table_ex:
                    info["values_table"] = f"error:{table_ex.__class__.__name__}"
                try:
                    session.query(History.id).limit(1).all()
                    info["history_table"] = "ok"
                except Exception as table_ex:
                    info["history_table"] = f"error:{table_ex.__class__.__name__}"
            return True

        _, ms = _timed(_run)
        return _ok("database", ms=ms, detail={"state": "ok", **info})
    except Exception as ex:
        _logger.exception("probe_database failed")
        fail = _fail("database", str(ex))
        fail["detail"] = info
        return fail

def probe_objects_storage(sample_limit: int = 3) -> dict:
    """Проверка ObjectsStorage: число загруженных объектов и sample getObject."""
    try:
        from app.core.main.ObjectsStorage import objects_storage
        from app.core.lib.object import getObject

        started = time.perf_counter()
        # len() триггерит sync_missing — это намеренно
        loaded = len(objects_storage.objects)
        names = list(objects_storage.objects.keys())[: max(0, int(sample_limit))]
        sample_ms: list[float] = []
        for name in names:
            t0 = time.perf_counter()
            obj = getObject(name)
            sample_ms.append((time.perf_counter() - t0) * 1000.0)
            if obj is None:
                return _fail(
                    "objects_storage",
                    f"getObject({name!r}) returned None",
                    ms=(time.perf_counter() - started) * 1000.0,
                )
        total_ms = (time.perf_counter() - started) * 1000.0
        avg_get = round(statistics.mean(sample_ms), 3) if sample_ms else 0.0
        return _ok(
            "objects_storage",
            ms=total_ms,
            detail={
                "objects_loaded": loaded,
                "sample_names": names,
                "avg_get_object_ms": avg_get,
            },
        )
    except Exception as ex:
        _logger.exception("probe_objects_storage failed")
        return _fail("objects_storage", str(ex))


def probe_thread_pools() -> dict:
    """Здоровье пулов: linkedProperty router + say/notify/playsound."""
    try:
        started = time.perf_counter()
        pools: dict[str, Any] = {}
        unhealthy: list[str] = []

        from app.core.main import ObjectManager as om_mod

        router = getattr(om_mod, "_poolLinkedProperty", None)
        if router is not None:
            stats = router.get_stats()
            pools["linkedProperty"] = {
                "router_name": stats.get("router_name"),
                "routing_thresholds": stats.get("routing_thresholds"),
            }
            for pool_key in ("safe_pool", "medium_pool", "trusted_pool"):
                mon = (stats.get(pool_key) or {}).get("thread_pool") or {}
                pools[f"linkedProperty.{pool_key}"] = {
                    "active_tasks": len(mon.get("active_tasks") or {}),
                    "completed_tasks": mon.get("completed_tasks"),
                    "failed_tasks": mon.get("failed_tasks"),
                    "rejected_tasks": mon.get("rejected_tasks"),
                    "queue_size": mon.get("queue_size"),
                    "pool_utilization": mon.get("pool_utilization"),
                }
            for attr, label in (
                ("_safe_pool", "linkedProperty.safe"),
                ("_medium_pool", "linkedProperty.medium"),
                ("_trusted_pool", "linkedProperty.trusted"),
            ):
                pool = getattr(router, attr, None)
                if pool is not None and hasattr(pool, "is_healthy") and not pool.is_healthy():
                    unhealthy.append(label)

        try:
            from app.core.lib import common as common_mod

            for attr, label in (
                ("_poolSay", "say"),
                ("_poolPlaysound", "playsound"),
                ("_poolNotify", "notify"),
            ):
                pool = getattr(common_mod, attr, None)
                if pool is None:
                    continue
                st = pool.get_stats()
                pools[label] = {
                    "active_threads": st.active_threads,
                    "pending_tasks": st.pending_tasks,
                    "completed_tasks": st.completed_tasks,
                    "failed_tasks": st.failed_tasks,
                    "rejected_tasks": st.rejected_tasks,
                    "pool_utilization": st.pool_utilization,
                }
                if hasattr(pool, "is_healthy") and not pool.is_healthy():
                    unhealthy.append(label)
        except Exception as ex:
            pools["common_pools_error"] = str(ex)

        ms = (time.perf_counter() - started) * 1000.0
        if unhealthy:
            return {
                "name": "thread_pools",
                "ok": False,
                "ms": round(ms, 3),
                "error": "unhealthy pools: " + ", ".join(unhealthy),
                "detail": {"pools": pools, "unhealthy": unhealthy},
            }
        return _ok("thread_pools", ms=ms, detail={"pools": pools})
    except Exception as ex:
        _logger.exception("probe_thread_pools failed")
        return _fail("thread_pools", str(ex))


def probe_batch_writer_stats() -> dict:
    """Статистика глобального BatchWriter."""
    try:
        from app.core.main.ObjectManager import get_batch_writer_stats

        started = time.perf_counter()
        stats = get_batch_writer_stats()
        ms = (time.perf_counter() - started) * 1000.0
        warning = None
        if stats.get("last_error"):
            warning = f"last_error={stats.get('last_error')}"
        if not stats.get("worker_thread_alive", True):
            return _fail("batch_writer", "worker thread is not alive", ms=ms)
        return _ok(
            "batch_writer",
            ms=ms,
            detail={
                "current_batch_size": stats.get("current_batch_size"),
                "total_added": stats.get("total_added"),
                "total_flushed": stats.get("total_flushed"),
                "total_errors": stats.get("total_errors"),
                "execution_time": stats.get("execution_time"),
                "external": stats.get("external"),
            },
            warning=warning,
        )
    except Exception as ex:
        _logger.exception("probe_batch_writer_stats failed")
        return _fail("batch_writer", str(ex))


def _assert_sandbox_name(object_name: str) -> None:
    if not object_name or not str(object_name).startswith(SANDBOX_OBJECT_PREFIX):
        raise PermissionError(
            f"Write-probe разрешён только для объектов с префиксом {SANDBOX_OBJECT_PREFIX!r}, "
            f"получено: {object_name!r}"
        )


def _object_has_external_links(obj) -> list[str]:
    """Вернуть список linked-плагинов у свойств объекта (если есть)."""
    links: list[str] = []
    props = getattr(obj, "properties", None) or {}
    for prop_name, prop in props.items():
        linked = getattr(prop, "linked", None)
        if not linked:
            value = getattr(prop, "value", None)
            linked = getattr(value, "linked", None) if value is not None else None
        if linked:
            if isinstance(linked, (list, tuple, set)):
                for item in linked:
                    links.append(f"{prop_name}:{item}")
            else:
                links.append(f"{prop_name}:{linked}")
    return links


def _latency_stats(latencies: list[float]) -> dict:
    sorted_lat = sorted(latencies)
    p50 = sorted_lat[len(sorted_lat) // 2]
    p95 = sorted_lat[max(0, int(len(sorted_lat) * 0.95) - 1)]
    return {
        "avg": round(statistics.mean(latencies), 3),
        "p50": round(p50, 3),
        "p95": round(p95, 3),
        "max": round(max(latencies), 3),
        "min": round(min(latencies), 3),
    }


def probe_property_roundtrip(
    object_name: str,
    property_name: str = "probe",
    value: Any = None,
    *,
    iterations: int = 1,
    save_history: bool = False,
    flush_batch: bool = False,
    source: str = "osysHome:diagnostics",
    check_name: str = "property_roundtrip",
) -> dict:
    """Write→read roundtrip на sandbox-объекте с замером latency.

    При ``save_history=True`` + ``flush_batch=True`` пишет историю в
    настроенную БД пользователя через BatchWriter.flush_sync().
    """
    iterations = max(1, int(iterations))
    if value is None:
        value = f"probe-{int(time.time())}"

    try:
        _assert_sandbox_name(object_name)
        from app.core.lib.object import getObject, getProperty, setProperty

        obj = getObject(object_name)
        if obj is None:
            return _fail(check_name, f"Object not found: {object_name}")

        links = _object_has_external_links(obj)
        if links:
            return _fail(
                check_name,
                "Sandbox object has external links: " + ", ".join(links[:10]),
            )

        if property_name not in (getattr(obj, "properties", None) or {}):
            return _fail(
                check_name,
                f"Property not found: {object_name}.{property_name}",
            )

        latencies: list[float] = []
        flush_latencies: list[float] = []
        for i in range(iterations):
            write_val = value if iterations == 1 else f"{value}-{i}"
            t0 = time.perf_counter()
            ok = setProperty(
                f"{object_name}.{property_name}",
                write_val,
                source=source,
                save_history=save_history,
                track_stats=False,
            )
            if not ok:
                return _fail(check_name, "setProperty returned False")
            if flush_batch:
                from app.core.main.ObjectManager import flush_batch_writer_sync

                t_flush = time.perf_counter()
                flush_batch_writer_sync()
                flush_latencies.append((time.perf_counter() - t_flush) * 1000.0)
            read_val = getProperty(f"{object_name}.{property_name}")
            latencies.append((time.perf_counter() - t0) * 1000.0)
            if str(read_val) != str(write_val):
                return _fail(
                    check_name,
                    f"value mismatch: wrote {write_val!r}, read {read_val!r}",
                    ms=latencies[-1],
                )

        detail = {
            "object": object_name,
            "property": property_name,
            "iterations": iterations,
            "save_history": save_history,
            "flush_batch": flush_batch,
            "db": _db_connection_info(),
            "latency_ms": _latency_stats(latencies),
        }
        if flush_latencies:
            detail["flush_latency_ms"] = _latency_stats(flush_latencies)
        return _ok(
            check_name,
            ms=round(statistics.mean(latencies), 3),
            detail=detail,
        )
    except PermissionError as ex:
        return _fail(check_name, str(ex))
    except Exception as ex:
        _logger.exception("probe_property_roundtrip failed")
        return _fail(check_name, str(ex))


def probe_history_roundtrip(
    object_name: str,
    property_name: str = "probe_hist",
    *,
    iterations: int = 3,
    cleanup_rows: bool = True,
    source: str = "osysHome:diagnostics",
) -> dict:
    """Запись истории свойства в реальную БД пользователя + проверка строк History."""
    try:
        _assert_sandbox_name(object_name)
        from app.core.lib.object import getObject
        from app.core.models.Clasess import History

        obj = getObject(object_name)
        if obj is None:
            return _fail("history_roundtrip", f"Object not found: {object_name}")
        prop = (getattr(obj, "properties", None) or {}).get(property_name)
        if prop is None:
            return _fail(
                "history_roundtrip",
                f"Property not found: {object_name}.{property_name}",
            )
        value_id = getattr(prop, "value_id", None)
        if not value_id:
            return _fail("history_roundtrip", "Property has no value_id")

        from app.database import get_now_to_utc

        probe_started = get_now_to_utc()
        with session_scope() as session:
            before_ids = {
                row.id
                for row in session.query(History.id)
                .filter(History.value_id == value_id, History.source == source)
                .all()
            }

        write_result = probe_property_roundtrip(
            object_name,
            property_name,
            value=f"hist-{int(time.time())}",
            iterations=iterations,
            save_history=True,
            flush_batch=True,
            source=source,
            check_name="history_roundtrip",
        )
        if not write_result.get("ok"):
            return write_result

        with session_scope() as session:
            after_rows = (
                session.query(History)
                .filter(History.value_id == value_id, History.source == source)
                .all()
            )
            new_ids = [row.id for row in after_rows if row.id not in before_ids]
            inserted = len(new_ids)
            # На случай рассинхрона часов — также строки с added >= probe_started
            if inserted < iterations:
                new_ids = [
                    row.id
                    for row in after_rows
                    if row.id not in before_ids
                    or (row.added and row.added >= probe_started)
                ]
                inserted = len({*new_ids})
            if cleanup_rows and new_ids:
                session.query(History).filter(History.id.in_(new_ids)).delete(
                    synchronize_session=False
                )
                session.commit()

        if inserted < iterations:
            return _fail(
                "history_roundtrip",
                f"Expected >= {iterations} history rows in user DB, got {inserted}",
                ms=write_result.get("ms", 0),
            )

        detail = dict(write_result.get("detail") or {})
        detail["history_rows_inserted"] = inserted
        detail["history_cleanup"] = bool(cleanup_rows)
        return _ok(
            "history_roundtrip",
            ms=write_result.get("ms", 0),
            detail=detail,
        )
    except PermissionError as ex:
        return _fail("history_roundtrip", str(ex))
    except Exception as ex:
        _logger.exception("probe_history_roundtrip failed")
        return _fail("history_roundtrip", str(ex))

def probe_method_invoke(
    object_name: str,
    method_name: str = "ping",
    *,
    source: str = "osysHome:diagnostics",
) -> dict:
    """Вызов безопасного метода sandbox-объекта с замером latency."""
    try:
        _assert_sandbox_name(object_name)
        from app.core.lib.object import callMethod, getObject

        obj = getObject(object_name)
        if obj is None:
            return _fail("method_invoke", f"Object not found: {object_name}")

        links = _object_has_external_links(obj)
        if links:
            return _fail(
                "method_invoke",
                "Sandbox object has external links: " + ", ".join(links[:10]),
            )

        methods = getattr(obj, "methods", None) or {}
        if method_name not in methods:
            return _fail(
                "method_invoke",
                f"Method not found: {object_name}.{method_name}",
            )

        def _run():
            return callMethod(f"{object_name}.{method_name}", args={}, source=source)

        result, ms = _timed(_run)
        return _ok(
            "method_invoke",
            ms=ms,
            detail={"object": object_name, "method": method_name, "result": str(result)[:500]},
        )
    except PermissionError as ex:
        return _fail("method_invoke", str(ex))
    except Exception as ex:
        _logger.exception("probe_method_invoke failed")
        return _fail("method_invoke", str(ex))
