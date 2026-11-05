# Триггеры БД (`__db_triggers__`)

osysHome умеет ставить **произвольные SQL-триггеры**, объявленные на моделях SQLAlchemy. Установка идемпотентна в конце каждого вызова `sync_db(app)` (таблицы ядра и повторно после плагинов).

Защита сущностей (`params.protected`) использует тот же механизм через фабрику `protected_triggers(...)`.

## Как это работает

1. Модель задаёт `__db_triggers__` — последовательность объектов `DbTrigger`.
2. `sync_db` завершает синхронизацию схемы и вызывает `sync_model_triggers(engine)`.
3. Установщик обходит `db.Model.registry` и для каждой модели с `__db_triggers__` выполняет `DROP IF EXISTS` + `CREATE` под текущий диалект (`sqlite`, `postgresql`, `mysql`).

Плагины загружаются между двумя вызовами `sync_db`, поэтому их модели тоже могут объявить триггеры — второй проход их установит.

См. также: [BOOT_SEQUENCE.ru.md](BOOT_SEQUENCE.ru.md), [ARCHITECTURE.md](ARCHITECTURE.md).

## `DbTrigger`

Определён в `app/database.py`:

```python
from app.db_tools import DbTrigger

DbTrigger(
    name="block_name",          # в БД: trg_<table>_<name>
    timing="BEFORE",            # BEFORE | AFTER
    event="UPDATE",             # INSERT | UPDATE | DELETE
    body={
        "sqlite": "...",        # внутри CREATE TRIGGER ... BEGIN <body> END
        "postgresql": "...",    # тело plpgsql-функции (BEGIN ... RETURN ... END)
        "mysql": "...",         # внутри CREATE TRIGGER ... BEGIN <body> END
    },
)
```

- Нет `body[dialect]` → warning и пропуск для этого диалекта.
- Неизвестный диалект → warning и пропуск.

### Пример произвольного триггера

```python
from app.database import Column, SurrogatePK, db
from app.db_tools import DbTrigger

class AuditRow(SurrogatePK, db.Model):
    __tablename__ = "audit_rows"
    __db_triggers__ = (
        DbTrigger(
            name="deny_update",
            timing="BEFORE",
            event="UPDATE",
            body={
                "sqlite": "SELECT RAISE(ABORT, 'audit rows are immutable');",
                "postgresql": "BEGIN RAISE EXCEPTION 'audit rows are immutable'; END;",
                "mysql": "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit rows are immutable';",
            },
        ),
    )
    payload = Column(db.Text)
```

## `protected_triggers(...)` (частный случай)

Фабрика UPDATE (+ опционально DELETE) с проверкой `params.protected`:

```python
from app.db_tools import protected_triggers

__db_triggers__ = protected_triggers(
    immutable_columns=("name", "class_id"),
    protect_delete=True,       # по умолчанию
    params_column="params",    # по умолчанию
)
```

Если у **старой** строки `params.protected` истинно:

| Действие | Результат |
|----------|-----------|
| Изменение любой из `immutable_columns` | Отказ |
| Снятие / удаление `protected` | Отказ |
| `DELETE` (если `protect_delete`) | Отказ |
| Смена description и прочих колонок | Разрешено |
| Добавление других ключей в `params` (с сохранением `protected`) | Разрешено |
| Установка `protected` на незащищённой строке | Разрешено |

### Модели ядра

В `app/core/models/Clasess.py`:

| Модель | Неизменяемые колонки |
|--------|----------------------|
| `Class` | `name`, `parent_id` |
| `Object` | `name`, `class_id` |
| `Property` | `name`, `class_id`, `object_id`, `type` |
| `Method` | `name`, `class_id`, `object_id` |

Проверки на уровне приложения (`mark*Protected`, delete в `object.py` / `entity_params.py`) остаются для понятных ошибок UX. Триггеры — **defense in depth** против сырого SQL и обхода Python-проверок.

## Комбинация фабрики и своих триггеров

```python
__db_triggers__ = (
    *protected_triggers(immutable_columns=("name",)),
    DbTrigger(name="after_insert_hook", timing="AFTER", event="INSERT", body={...}),
)
```

## Ограничения

- Админ БД может сделать `DROP TRIGGER` — это не граница безопасности против привилегированного доступа к СУБД.
- Для каждого диалекта нужен свой SQL в `body` (или фабрика, генерирующая все три).
- Намеренное снятие защиты — только временным отключением триггера (встроенного bypass нет).

## Связанные материалы

- `app/db_tools/sync_db.py` — `DbTrigger`, `sync_db`, `sync_model_triggers`
- `app/db_tools/protected.py` — `protected_triggers`
- `app/core/lib/entity_params.py` — Python-хелперы для `params.protected`
- [PARAMS_DOCUMENTATION.md](PARAMS_DOCUMENTATION.md) — схемы `params` свойств
