"""Синхронизация схемы БД и установка model triggers."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import ForeignKey, inspect, text
from sqlalchemy.exc import ProgrammingError

from app.extensions import db
from app.logging_config import getLogger

logger = getLogger("db_tools")


def normalize_column_type(column_type, dialect):
    column_type_str = str(column_type).upper()

    type_mappings = {
        "mysql": {
            "TINYINT(1)": "BOOLEAN",
            "TINYINT": "BOOLEAN",
            "MEDIUMINT": "INTEGER",
            "BIGINT": "BIGINTEGER",
            "VARCHAR": "STRING",
            "TEXT": "MEDIUMTEXT",
        },
        "sqlite": {
            "BOOLEAN": "INTEGER",
            "BIGINTEGER": "INTEGER",
        },
        "postgresql": {
            "BOOLEAN": "BOOLEAN",
            "DOUBLE PRECISION": "FLOAT",
            "INTEGER": "INTEGER",
            "BIGINT": "BIGINTEGER",
            "TEXT": "TEXT",
            "VARCHAR": "STRING",
            "DATETIME": "TIMESTAMP",
            "TIMESTAMP": "TIMESTAMP",
        },
    }

    return type_mappings.get(dialect, {}).get(column_type_str, column_type_str)


@dataclass(frozen=True)
class DbTrigger:
    """Декларация DB-триггера для модели (``__db_triggers__``).

    ``body`` — SQL по диалекту (``sqlite`` / ``postgresql`` / ``mysql``):
    - sqlite/mysql: фрагмент внутри ``CREATE TRIGGER ... BEGIN <body> END``;
    - postgresql: тело plpgsql-функции (включая ``BEGIN``/``RETURN``/``END``).
    """

    name: str
    timing: str
    event: str
    body: dict[str, str]


def _trigger_full_name(table_name: str, trigger_name: str) -> str:
    return f"trg_{table_name}_{trigger_name}"


def _normalize_sql(sql: str | None) -> str:
    """Сжимает пробелы для сравнения определений триггера."""
    if not sql:
        return ""
    return " ".join(str(sql).split()).strip().lower()


def _build_trigger_create_sql(
    dialect: str, table_name: str, trg_name: str, timing: str, event: str, body: str
) -> str:
    """Канонический CREATE TRIGGER (для сравнения и установки)."""
    if dialect == "sqlite":
        return (
            f"CREATE TRIGGER {trg_name} {timing} {event} ON {table_name} "
            f"FOR EACH ROW BEGIN {body} END"
        )
    if dialect == "postgresql":
        return (
            f'CREATE TRIGGER "{trg_name}" {timing} {event} ON "{table_name}" '
            f'FOR EACH ROW EXECUTE PROCEDURE "{trg_name}_fn"()'
        )
    if dialect == "mysql":
        return (
            f"CREATE TRIGGER `{trg_name}` {timing} {event} ON `{table_name}` "
            f"FOR EACH ROW BEGIN {body} END"
        )
    raise ValueError(f"unsupported dialect: {dialect}")


def _fetch_existing_trigger_sql(conn, dialect: str, table_name: str, trg_name: str) -> str | None:
    """Текущее определение триггера в БД или None."""
    if dialect == "sqlite":
        row = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=:n"),
            {"n": trg_name},
        ).fetchone()
        return row[0] if row and row[0] else None

    if dialect == "postgresql":
        row = conn.execute(
            text(
                "SELECT pg_get_triggerdef(t.oid, true) "
                "FROM pg_trigger t "
                "JOIN pg_class c ON c.oid = t.tgrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE NOT t.tgisinternal AND t.tgname = :n AND c.relname = :tbl "
                "AND n.nspname = current_schema()"
            ),
            {"n": trg_name, "tbl": table_name},
        ).fetchone()
        return row[0] if row and row[0] else None

    if dialect == "mysql":
        row = conn.execute(
            text(
                "SELECT ACTION_STATEMENT, ACTION_TIMING, EVENT_MANIPULATION, EVENT_OBJECT_TABLE "
                "FROM information_schema.TRIGGERS "
                "WHERE TRIGGER_SCHEMA = DATABASE() AND TRIGGER_NAME = :n"
            ),
            {"n": trg_name},
        ).fetchone()
        if not row:
            return None
        action, timing, event, tbl = row
        # Собираем сопоставимую форму с нашим CREATE
        return (
            f"CREATE TRIGGER `{trg_name}` {timing} {event} ON `{tbl}` "
            f"FOR EACH ROW {action}"
        )

    return None


def _fetch_existing_pg_function_body(conn, fn_name: str) -> str | None:
    """Тело plpgsql-функции триггера (для сравнения с body)."""
    row = conn.execute(
        text(
            "SELECT prosrc FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE p.proname = :n AND n.nspname = current_schema()"
        ),
        {"n": fn_name},
    ).fetchone()
    return row[0] if row and row[0] else None


def _install_db_trigger(conn, dialect: str, table_name: str, trigger: DbTrigger) -> bool:
    """Создаёт/обновляет триггер. True только если реально создан или изменён."""
    body = (trigger.body or {}).get(dialect)
    if not body:
        logger.warning(
            "⚠ Нет body для dialect=%s, триггер %s на %s пропущен",
            dialect,
            trigger.name,
            table_name,
        )
        return False

    trg_name = _trigger_full_name(table_name, trigger.name)
    timing = (trigger.timing or "BEFORE").upper()
    event = (trigger.event or "UPDATE").upper()
    if timing not in ("BEFORE", "AFTER") or event not in ("INSERT", "UPDATE", "DELETE"):
        logger.warning(
            "⚠ Некорректные timing/event у триггера %s.%s: %s %s",
            table_name,
            trigger.name,
            timing,
            event,
        )
        return False

    desired = _build_trigger_create_sql(
        dialect, table_name, trg_name, timing, event, body
    )
    existing = _fetch_existing_trigger_sql(conn, dialect, table_name, trg_name)

    if dialect == "postgresql":
        fn_name = f"{trg_name}_fn"
        existing_fn = _fetch_existing_pg_function_body(conn, fn_name)
        same_fn = _normalize_sql(existing_fn) == _normalize_sql(body)
        same_trg = _normalize_sql(existing) == _normalize_sql(desired)
        if existing and existing_fn and same_fn and same_trg:
            return False
    elif existing and _normalize_sql(existing) == _normalize_sql(desired):
        return False

    try:
        if dialect == "sqlite":
            conn.execute(text(f"DROP TRIGGER IF EXISTS {trg_name}"))
            conn.execute(text(desired))
        elif dialect == "postgresql":
            fn_name = f"{trg_name}_fn"
            quoted_table = f'"{table_name}"'
            conn.execute(text(f'DROP TRIGGER IF EXISTS "{trg_name}" ON {quoted_table}'))
            conn.execute(text(f'DROP FUNCTION IF EXISTS "{fn_name}"()'))
            conn.execute(
                text(
                    f'CREATE OR REPLACE FUNCTION "{fn_name}"() RETURNS TRIGGER AS $trg$ '
                    f"{body} $trg$ LANGUAGE plpgsql"
                )
            )
            conn.execute(text(desired))
        elif dialect == "mysql":
            conn.execute(text(f"DROP TRIGGER IF EXISTS `{trg_name}`"))
            conn.execute(text(desired))
        else:
            logger.warning("⚠ Неизвестный dialect=%s, триггеры не ставятся", dialect)
            return False
        return True
    except Exception:
        logger.exception(
            "❌ Ошибка установки триггера %s на %s (%s)", trg_name, table_name, dialect
        )
        return False


def sync_model_triggers(engine) -> None:
    """Идемпотентно создаёт триггеры из ``Model.__db_triggers__``."""
    dialect = engine.dialect.name
    if dialect not in ("sqlite", "postgresql", "mysql"):
        logger.warning("⚠ sync_model_triggers: dialect %s не поддерживается", dialect)
        return

    installed = 0
    with engine.connect() as conn:
        for _key, model in list(db.Model.registry._class_registry.items()):
            if not isinstance(model, type):
                continue
            if not getattr(model, "__tablename__", None):
                continue
            triggers = getattr(model, "__db_triggers__", None)
            if not triggers:
                continue
            table_name = model.__tablename__
            for trigger in triggers:
                if not isinstance(trigger, DbTrigger):
                    logger.warning(
                        "⚠ %s.__db_triggers__ содержит не DbTrigger: %r",
                        table_name,
                        trigger,
                    )
                    continue
                if _install_db_trigger(conn, dialect, table_name, trigger):
                    installed += 1
                    logger.info(
                        "✅ Trigger %s on %s (%s %s)",
                        _trigger_full_name(table_name, trigger.name),
                        table_name,
                        trigger.timing,
                        trigger.event,
                    )
        conn.commit()
    if installed:
        logger.info("✅ sync_model_triggers: установлено %s триггеров", installed)


def sync_db(app):
    """Синхронизация таблиц/колонок/FK и model triggers."""
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)
        dialect = engine.dialect.name  # mysql, postgresql, sqlite

        for _class_name, model in db.Model.registry._class_registry.items():
            if hasattr(model, "__tablename__") and hasattr(model, "__table__"):
                table_name = model.__tablename__
                safe_table_name = (
                    f'"{table_name}"' if dialect == "postgresql" else f"`{table_name}`"
                )

                if not inspector.has_table(table_name):
                    logger.info(f"✅ Create table: {table_name}")
                    model.__table__.create(engine)
                else:
                    existing_columns = {
                        col["name"]: col for col in inspector.get_columns(table_name)
                    }
                    existing_foreign_keys = {
                        fk["constrained_columns"][0]
                        for fk in inspector.get_foreign_keys(table_name)
                    }

                    # Step 1: Add new columns
                    for column in model.__table__.columns:
                        if column.name not in existing_columns:
                            safe_column_name = (
                                f'"{column.name}"'
                                if dialect == "postgresql"
                                else f"`{column.name}`"
                            )
                            column_type = normalize_column_type(column.type, dialect)

                            if dialect == "sqlite":
                                logger.info(f"⚠ SQLite: add column {column.name}")
                                alter_stmt = text(
                                    f"ALTER TABLE {table_name} ADD COLUMN {column.name}"
                                )
                            else:
                                alter_stmt = text(
                                    f"ALTER TABLE {safe_table_name} "
                                    f"ADD COLUMN {safe_column_name} {column_type}"
                                )

                            with engine.connect() as conn:
                                conn.execute(alter_stmt)
                                conn.commit()
                            logger.info(
                                f"✅ Column {column.name} added in {table_name}"
                            )

                    # Step 2: Check and change column types if necessary
                    for column in model.__table__.columns:
                        if column.name in existing_columns:
                            db_column_type = existing_columns[column.name]["type"]
                            column_type = normalize_column_type(column.type, dialect)
                            if (
                                normalize_column_type(db_column_type, dialect)
                                != column_type
                            ):
                                if dialect == "sqlite":
                                    logger.warning(
                                        f"⚠ SQLite: no change type in "
                                        f"{table_name}.{column.name}"
                                    )
                                    continue
                                safe_column_name = (
                                    f'"{column.name}"'
                                    if dialect == "postgresql"
                                    else f"`{column.name}`"
                                )
                                if dialect == "postgresql":
                                    alter_stmt = text(
                                        f"ALTER TABLE {safe_table_name} "
                                        f"ALTER COLUMN {safe_column_name} "
                                        f"TYPE {column_type}"
                                    )
                                elif dialect == "mysql":
                                    alter_stmt = text(
                                        f"ALTER TABLE {safe_table_name} "
                                        f"MODIFY COLUMN {safe_column_name} "
                                        f"{column_type}"
                                    )
                                with engine.connect() as conn:
                                    conn.execute(alter_stmt)
                                    conn.commit()
                                logger.info(
                                    f"✅ Changed type column {column.name} "
                                    f"in {table_name} of {column_type}"
                                )

                    # Step 3: Remove columns that are no longer present in the model
                    for db_column in existing_columns.values():
                        if db_column["name"] not in model.__table__.columns:
                            try:
                                alter_stmt = text(
                                    f"ALTER TABLE {safe_table_name} "
                                    f"DROP COLUMN {db_column['name']}"
                                )
                                with engine.connect() as conn:
                                    conn.execute(alter_stmt)
                                    conn.commit()
                                logger.info(
                                    f"✅ Deleted column {db_column['name']} "
                                    f"in {table_name}"
                                )
                            except ProgrammingError as e:
                                logger.error(
                                    f"❌ Error delete column {db_column['name']} "
                                    f"in {table_name}: {e}"
                                )

                    # Step 4: Check and create/update foreign keys
                    for column in model.__table__.columns:
                        if isinstance(column.type, ForeignKey):
                            fk_name = f"fk_{table_name}_{column.name}"
                            referenced_table = column.type.target_fullname.split(".")[0]
                            referenced_column = column.type.target_fullname.split(".")[1]

                            if fk_name not in existing_foreign_keys:
                                logger.info(
                                    f"🔗 Add foreignkey: {table_name}.{column.name} "
                                    f"→ {referenced_table}.{referenced_column}"
                                )
                                alter_stmt = text(
                                    f"ALTER TABLE {safe_table_name} "
                                    f"ADD CONSTRAINT {fk_name} "
                                    f"FOREIGN KEY ({column.name}) "
                                    f"REFERENCES {referenced_table} "
                                    f"({referenced_column})"
                                )
                                with engine.connect() as conn:
                                    conn.execute(alter_stmt)
                                    conn.commit()
                                logger.info(
                                    f"✅ Foreignkey {table_name}.{column.name} "
                                    f"→ {referenced_table}.{referenced_column} added"
                                )

                    # Step 5: Remove unnecessary foreign keys
                    if dialect != "sqlite":
                        for fk in inspector.get_foreign_keys(table_name):
                            fk_name = fk["name"]
                            expected = [
                                f"fk_{table_name}_{column.name}"
                                for column in model.__table__.columns
                                if isinstance(column.type, ForeignKey)
                            ]
                            if fk_name not in expected:
                                try:
                                    alter_stmt = text(
                                        f"ALTER TABLE {safe_table_name} "
                                        f"DROP CONSTRAINT {fk_name}"
                                    )
                                    with engine.connect() as conn:
                                        conn.execute(alter_stmt)
                                        conn.commit()
                                    logger.info(
                                        f"✅ Deleted foreignkey {fk_name} "
                                        f"in {table_name}"
                                    )
                                except ProgrammingError as e:
                                    logger.error(
                                        f"❌ Error delete foreignkey {fk_name} "
                                        f"in {table_name}: {e}"
                                    )

        # Step 6: model triggers (__db_triggers__)
        sync_model_triggers(engine)
