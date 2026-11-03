"""Фабрика protected-триггеров (``params.protected``)."""
from __future__ import annotations

from app.db_tools.sync_db import DbTrigger


def _protected_flag_expr(dialect: str, row_alias: str, params_column: str) -> str:
    """SQL: True, если в params выставлен protected (отсутствие ключа = false)."""
    col = f"{row_alias}.{params_column}"
    if dialect == "sqlite":
        # COALESCE: иначе NOT (NULL IN (...)) даёт NULL и WHEN не срабатывает
        return (
            f"COALESCE(json_extract({col}, '$.protected'), 0) "
            f"IN (1, '1', 'true', 'True')"
        )
    if dialect == "postgresql":
        return f"COALESCE(({col})::json->>'protected', '') IN ('true', '1', 'True')"
    if dialect == "mysql":
        return (
            f"COALESCE(JSON_UNQUOTE(JSON_EXTRACT({col}, '$.protected')), '') "
            f"IN ('true', '1', 'True')"
        )
    raise ValueError(f"unsupported dialect: {dialect}")


def _col_changed_expr(dialect: str, column: str) -> str:
    """Null-safe: колонка изменилась между OLD и NEW."""
    if dialect == "sqlite":
        return f"NEW.{column} IS NOT OLD.{column}"
    if dialect == "postgresql":
        return f"NEW.{column} IS DISTINCT FROM OLD.{column}"
    if dialect == "mysql":
        return f"NOT (NEW.{column} <=> OLD.{column})"
    raise ValueError(f"unsupported dialect: {dialect}")


def _protected_update_body(
    dialect: str,
    immutable_columns: tuple[str, ...],
    params_column: str,
) -> str:
    old_prot = _protected_flag_expr(dialect, "OLD", params_column)
    new_prot = _protected_flag_expr(dialect, "NEW", params_column)

    if dialect == "sqlite":
        parts = [f"WHEN NOT ({old_prot}) THEN NULL"]
        for col in immutable_columns:
            parts.append(
                f"WHEN {_col_changed_expr(dialect, col)} THEN "
                f"RAISE(ABORT, 'Entity is protected: cannot change {col}')"
            )
        parts.append(
            f"WHEN NOT ({new_prot}) THEN "
            f"RAISE(ABORT, 'Entity is protected: cannot clear protected flag')"
        )
        return "SELECT CASE " + " ".join(parts) + " END;"

    if dialect == "postgresql":
        lines = [
            "BEGIN",
            f"  IF NOT ({old_prot}) THEN",
            "    RETURN NEW;",
            "  END IF;",
        ]
        for col in immutable_columns:
            lines.append(f"  IF {_col_changed_expr(dialect, col)} THEN")
            lines.append(
                f"    RAISE EXCEPTION 'Entity is protected: cannot change {col}';"
            )
            lines.append("  END IF;")
        lines.append(f"  IF NOT ({new_prot}) THEN")
        lines.append(
            "    RAISE EXCEPTION 'Entity is protected: cannot clear protected flag';"
        )
        lines.append("  END IF;")
        lines.append("  RETURN NEW;")
        lines.append("END;")
        return "\n".join(lines)

    if dialect == "mysql":
        lines = [
            f"IF {old_prot} THEN",
        ]
        for col in immutable_columns:
            lines.append(f"  IF {_col_changed_expr(dialect, col)} THEN")
            lines.append(
                "    SIGNAL SQLSTATE '45000' "
                f"SET MESSAGE_TEXT = 'Entity is protected: cannot change {col}';"
            )
            lines.append("  END IF;")
        lines.append(f"  IF NOT ({new_prot}) THEN")
        lines.append(
            "    SIGNAL SQLSTATE '45000' "
            "SET MESSAGE_TEXT = 'Entity is protected: cannot clear protected flag';"
        )
        lines.append("  END IF;")
        lines.append("END IF;")
        return "\n".join(lines)

    raise ValueError(f"unsupported dialect: {dialect}")


def _protected_delete_body(dialect: str, params_column: str) -> str:
    old_prot = _protected_flag_expr(dialect, "OLD", params_column)
    if dialect == "sqlite":
        return (
            f"SELECT CASE WHEN {old_prot} THEN "
            f"RAISE(ABORT, 'Entity is protected: cannot delete') END;"
        )
    if dialect == "postgresql":
        return "\n".join(
            [
                "BEGIN",
                f"  IF {old_prot} THEN",
                "    RAISE EXCEPTION 'Entity is protected: cannot delete';",
                "  END IF;",
                "  RETURN OLD;",
                "END;",
            ]
        )
    if dialect == "mysql":
        return "\n".join(
            [
                f"IF {old_prot} THEN",
                "  SIGNAL SQLSTATE '45000' "
                "SET MESSAGE_TEXT = 'Entity is protected: cannot delete';",
                "END IF;",
            ]
        )
    raise ValueError(f"unsupported dialect: {dialect}")


def protected_triggers(
    *,
    immutable_columns: tuple[str, ...],
    protect_delete: bool = True,
    params_column: str = "params",
    name_prefix: str = "protected",
) -> tuple[DbTrigger, ...]:
    """Фабрика UPDATE/DELETE триггеров для ``params.protected``.

    Args:
        immutable_columns: Колонки, которые нельзя менять у защищённой строки.
        protect_delete: Блокировать DELETE защищённой строки.
        params_column: Колонка с JSON (флаг ``protected``).
        name_prefix: Суффикс имён триггеров (``trg_<table>_<prefix>_upd``).
    """
    dialects = ("sqlite", "postgresql", "mysql")
    update_body = {
        d: _protected_update_body(d, immutable_columns, params_column) for d in dialects
    }
    triggers: list[DbTrigger] = [
        DbTrigger(
            name=f"{name_prefix}_upd",
            timing="BEFORE",
            event="UPDATE",
            body=update_body,
        )
    ]
    if protect_delete:
        delete_body = {
            d: _protected_delete_body(d, params_column) for d in dialects
        }
        triggers.append(
            DbTrigger(
                name=f"{name_prefix}_del",
                timing="BEFORE",
                event="DELETE",
                body=delete_body,
            )
        )
    return tuple(triggers)
