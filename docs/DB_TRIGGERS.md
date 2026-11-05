# Database triggers (`__db_triggers__`)

osysHome can install **arbitrary SQL triggers** declared on SQLAlchemy models. Triggers are created idempotently at the end of every `sync_db(app)` pass (core tables and again after plugins).

Protected entities (`params.protected`) use the same mechanism via the `protected_triggers(...)` factory.

## How it works

1. A model defines `__db_triggers__` — a sequence of `DbTrigger` objects.
2. `sync_db` finishes schema sync, then calls `sync_model_triggers(engine)`.
3. The installer walks `db.Model.registry`, and for each model with `__db_triggers__` runs `DROP IF EXISTS` + `CREATE` for the current dialect (`sqlite`, `postgresql`, `mysql`).

Because plugins are loaded between the two `sync_db` calls, plugin models can declare triggers the same way; the second pass installs them.

See also: [BOOT_SEQUENCE.md](BOOT_SEQUENCE.md), [ARCHITECTURE.md](ARCHITECTURE.md).

## `DbTrigger`

Defined in `app/database.py`:

```python
from app.db_tools import DbTrigger

DbTrigger(
    name="block_name",          # becomes trg_<table>_<name>
    timing="BEFORE",            # BEFORE | AFTER
    event="UPDATE",             # INSERT | UPDATE | DELETE
    body={
        "sqlite": "...",        # inside CREATE TRIGGER ... BEGIN <body> END
        "postgresql": "...",    # plpgsql function body (BEGIN ... RETURN ... END)
        "mysql": "...",         # inside CREATE TRIGGER ... BEGIN <body> END
    },
)
```

- Missing `body[dialect]` → warning and skip for that dialect.
- Unknown dialect → warning and skip.

### Example: custom trigger

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

## `protected_triggers(...)` (special case)

Factory that returns UPDATE (+ optional DELETE) triggers enforcing `params.protected`:

```python
from app.db_tools import protected_triggers

__db_triggers__ = protected_triggers(
    immutable_columns=("name", "class_id"),
    protect_delete=True,       # default
    params_column="params",    # default
)
```

When `params.protected` is true on the **old** row:

| Action | Result |
|--------|--------|
| Change any `immutable_columns` | Abort |
| Clear / remove `protected` | Abort |
| `DELETE` (if `protect_delete`) | Abort |
| Change description / other columns | Allowed |
| Add other keys to `params` (keep `protected`) | Allowed |
| Set `protected` on an unprotected row | Allowed |

### Core models

Declared in `app/core/models/Clasess.py`:

| Model | Immutable columns |
|-------|-------------------|
| `Class` | `name`, `parent_id` |
| `Object` | `name`, `class_id` |
| `Property` | `name`, `class_id`, `object_id`, `type` |
| `Method` | `name`, `class_id`, `object_id` |

Application-level checks (`mark*Protected`, delete helpers in `object.py` / `entity_params.py`) remain for clear UX errors. Triggers are **defense in depth** against raw SQL and code paths that skip Python guards.

## Combining factory + custom triggers

```python
__db_triggers__ = (
    *protected_triggers(immutable_columns=("name",)),
    DbTrigger(name="after_insert_hook", timing="AFTER", event="INSERT", body={...}),
)
```

## Limitations

- A DB admin can still `DROP TRIGGER` — this is not a security boundary against privileged DB access.
- Each dialect needs its own SQL in `body` (or use a factory that generates all three).
- Removing protection intentionally requires temporarily dropping the trigger (or a privileged raw path) — there is no built-in bypass flag.

## Related

- `app/db_tools/sync_db.py` — `DbTrigger`, `sync_db`, `sync_model_triggers`
- `app/db_tools/protected.py` — `protected_triggers`
- `app/core/lib/entity_params.py` — Python helpers for `params.protected`
- [PARAMS_DOCUMENTATION.md](PARAMS_DOCUMENTATION.md) — property `params` schemas
