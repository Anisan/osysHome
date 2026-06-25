"""Database helpers for objects, properties, and related cleanup."""

from __future__ import annotations

from sqlalchemy import delete

from app.database import db
from app.core.lib.common import clearScheduledJob
from app.core.models.Clasess import Class, Object, Property, Method, Value, History


def get_descendant_class_ids(class_id: int) -> list[int]:
    """Return class_id and all descendant (child) class IDs down the tree."""
    root_id = int(class_id)
    ids = [root_id]
    queue = [root_id]
    visited = {root_id}

    while queue:
        parent_id = queue.pop(0)
        children = Class.query.filter(Class.parent_id == parent_id).all()
        for child in children:
            if child.id in visited:
                continue
            visited.add(child.id)
            ids.append(child.id)
            queue.append(child.id)

    return ids


def delete_object_from_db(object_id: int, *, clear_schedules: bool = True) -> str | None:
    """Delete object and all related rows. Returns object name or None if not found."""
    obj = Object.query.get(object_id)
    if not obj:
        return None

    name = obj.name

    value_ids = [
        row[0]
        for row in db.session.query(Value.id).filter(Value.object_id == object_id).all()
    ]
    if value_ids:
        db.session.execute(delete(History).where(History.value_id.in_(value_ids)))
    db.session.execute(delete(Value).where(Value.object_id == object_id))
    db.session.execute(delete(Property).where(Property.object_id == object_id))
    db.session.execute(delete(Method).where(Method.object_id == object_id))
    db.session.execute(delete(Object).where(Object.id == object_id))

    if clear_schedules:
        clearScheduledJob(name + r"\_%")  # noqa: W605

    return name


def delete_objects_by_class(class_id: int) -> list[str]:
    """Delete all objects in class tree (class and descendants). Returns deleted names."""
    class_ids = get_descendant_class_ids(class_id)
    objects = Object.query.filter(Object.class_id.in_(class_ids)).order_by(Object.name).all()
    deleted = []
    for obj in objects:
        name = delete_object_from_db(obj.id)
        if name:
            deleted.append(name)
    return deleted


def _orphan_object_query(model, object_ids: set[int]):
    query = model.query.filter(model.object_id.isnot(None))
    if object_ids:
        query = query.filter(~model.object_id.in_(object_ids))
    return query


def _orphan_class_query(model, class_ids: set[int]):
    query = model.query.filter(model.class_id.isnot(None), model.object_id.is_(None))
    if class_ids:
        query = query.filter(~model.class_id.in_(class_ids))
    return query


def cleanup_orphan_records() -> dict[str, int]:
    """Remove properties, methods, and values that reference missing objects/classes."""
    object_ids = {row[0] for row in db.session.query(Object.id).all()}
    class_ids = {row[0] for row in db.session.query(Class.id).all()}

    orphan_props = _orphan_object_query(Property, object_ids).all()
    orphan_methods = _orphan_object_query(Method, object_ids).all()
    orphan_values = _orphan_object_query(Value, object_ids).all()

    orphan_value_ids = [v.id for v in orphan_values]
    history_deleted = 0
    if orphan_value_ids:
        result = db.session.execute(delete(History).where(History.value_id.in_(orphan_value_ids)))
        history_deleted = result.rowcount or 0

    for val in orphan_values:
        db.session.delete(val)
    for prop in orphan_props:
        db.session.delete(prop)
    for method in orphan_methods:
        db.session.delete(method)

    stale_class_props = _orphan_class_query(Property, class_ids).all()
    stale_class_methods = _orphan_class_query(Method, class_ids).all()

    for prop in stale_class_props:
        db.session.delete(prop)
    for method in stale_class_methods:
        db.session.delete(method)

    return {
        'properties': len(orphan_props) + len(stale_class_props),
        'methods': len(orphan_methods) + len(stale_class_methods),
        'values': len(orphan_values),
        'history': history_deleted,
    }


def migrate_value_for_type_change(old_type: str | None, new_type: str | None, value: str | None) -> str | None:
    """Best-effort conversion of stored value when property type changes."""
    if value is None or value == '' or value == 'None':
        return value

    old_type = (old_type or '').strip()
    new_type = (new_type or '').strip()
    if not new_type or old_type == new_type:
        return value

    try:
        if new_type == 'int':
            if old_type == 'float':
                return str(int(float(value)))
            return str(int(value))
        if new_type == 'float':
            return str(float(value))
        if new_type == 'bool':
            lowered = str(value).strip().lower()
            if lowered in ('true', '1', 't', 'y', 'yes', 'on'):
                return 'True'
            if lowered in ('false', '0', 'f', 'n', 'no', 'off'):
                return 'False'
        if new_type == 'str':
            return str(value)
    except (TypeError, ValueError):
        return None
    return value


def migrate_values_for_property_type_change(
    property_name: str,
    old_type: str | None,
    new_type: str | None,
    *,
    object_id: int | None = None,
    class_id: int | None = None,
) -> int:
    """Update stored values after property type change. Returns count of updated rows."""
    if not property_name or (old_type or '') == (new_type or ''):
        return 0

    query = Value.query.filter(Value.name == property_name)
    if object_id:
        query = query.filter(Value.object_id == object_id)
    elif class_id:
        object_ids = [
            row[0]
            for row in db.session.query(Object.id).filter(
                Object.class_id.in_(get_descendant_class_ids(class_id))
            ).all()
        ]
        if not object_ids:
            return 0
        query = query.filter(Value.object_id.in_(object_ids))
    else:
        return 0

    updated = 0
    for val in query.all():
        new_value = migrate_value_for_type_change(old_type, new_type, val.value)
        if new_value is None:
            val.value = 'None'
            updated += 1
        elif new_value != val.value:
            val.value = new_value
            updated += 1
    return updated
