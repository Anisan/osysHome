"""Параметры сущностей (params JSON) и флаг ``protected``."""
from __future__ import annotations

import json

from app.database import session_scope
from app.core.main.ObjectsStorage import objects_storage
from app.core.models.Clasess import Class, Object, Property, Method
from app.core.lib.object_tree import invalidate_objects_tree_cache


def parse_params_json(raw) -> dict:
    """Разбирает params из JSON-строки или dict; при ошибке — пустой dict."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def is_params_protected(raw) -> bool:
    """True, если в params выставлен ``protected``."""
    return bool(parse_params_json(raw).get("protected"))


def merge_entity_params(raw, patch: dict) -> str:
    """Объединяет patch в params (существующие ключи перезаписываются)."""
    params = parse_params_json(raw)
    params.update(patch)
    return json.dumps(params)


def fill_missing_entity_params(raw, patch: dict) -> str | None:
    """Дополняет params ключами из patch, которых ещё нет.

    Returns:
        JSON-строка при изменениях, иначе None.
    """
    if not patch:
        return None
    params = parse_params_json(raw)
    changed = False
    for key, value in patch.items():
        if key not in params:
            params[key] = value
            changed = True
    if not changed:
        return None
    return json.dumps(params)


def getProtectedObjectNames() -> frozenset:
    """Имена объектов, которые нельзя удалить/переименовать.

    объекты с ``params.protected``.
    """
    names = set()
    with session_scope() as session:
        for name, raw in session.query(Object.name, Object.params).all():
            if is_params_protected(raw):
                names.add(name)
    return frozenset(names)


def getProtectedClassNames() -> frozenset:
    """Имена классов с ``params.protected``."""
    with session_scope() as session:
        return frozenset(
            name
            for name, raw in session.query(Class.name, Class.params).all()
            if is_params_protected(raw)
        )


def isObjectProtected(name: str) -> bool:
    """True, если объект нельзя удалить/переименовать."""
    name = name or ""
    with session_scope() as session:
        obj = session.query(Object).filter(Object.name == name).one_or_none()
        if not obj:
            return False
        return is_params_protected(obj.params)


def markObjectProtected(name: str) -> bool:
    """Выставляет ``params.protected`` у объекта.

    Args:
        name: Имя объекта.

    Returns:
        bool: True если объект найден и защита применена/уже была.
    """
    name = (name or "").strip()
    if not name:
        return False
    with session_scope() as session:
        obj = session.query(Object).filter(Object.name == name).one_or_none()
        if not obj:
            return False
        if is_params_protected(obj.params):
            return True
        obj.params = merge_entity_params(obj.params, {"protected": True})
        session.commit()
        object_id = obj.id
    objects_storage.reload_object(object_id)
    invalidate_objects_tree_cache()
    return True


def isClassProtected(name: str = None, class_id: int = None) -> bool:
    """True, если класс нельзя удалить/переименовать/сменить родителя."""
    with session_scope() as session:
        cls = None
        if class_id is not None:
            cls = session.query(Class).filter(Class.id == class_id).one_or_none()
        elif name:
            cls = session.query(Class).filter(Class.name == name).one_or_none()
        if not cls:
            return False
        return is_params_protected(cls.params)


def markClassProtected(name: str) -> bool:
    """Выставляет ``params.protected`` у класса."""
    name = (name or "").strip()
    if not name:
        return False
    with session_scope() as session:
        cls = session.query(Class).filter(Class.name == name).one_or_none()
        if not cls:
            return False
        if is_params_protected(cls.params):
            return True
        cls.params = merge_entity_params(cls.params, {"protected": True})
        session.commit()
        class_id = cls.id
    objects_storage.reload_objects_by_class(class_id)
    invalidate_objects_tree_cache()
    return True


def _split_qualified(name: str) -> tuple[str, str] | None:
    """Разбирает ``owner.member``; при ошибке — None."""
    try:
        owner, member = (name or "").split(".", 1)
    except ValueError:
        return None
    owner, member = owner.strip(), member.strip()
    if not owner or not member:
        return None
    return owner, member


def isObjectPropertyProtected(object_property: str) -> bool:
    """True, если свойство объекта имеет ``params.protected``."""
    parts = _split_qualified(object_property)
    if not parts:
        return False
    object_name, property_name = parts
    with session_scope() as session:
        obj = session.query(Object).filter(Object.name == object_name).one_or_none()
        if not obj:
            return False
        prop = session.query(Property).filter(
            Property.name == property_name, Property.object_id == obj.id
        ).one_or_none()
        if not prop:
            return False
        return is_params_protected(prop.params)


def markObjectPropertyProtected(object_property: str) -> bool:
    """Выставляет ``params.protected`` у свойства объекта (``Obj.prop``)."""
    parts = _split_qualified(object_property)
    if not parts:
        return False
    object_name, property_name = parts
    with session_scope() as session:
        obj = session.query(Object).filter(Object.name == object_name).one_or_none()
        if not obj:
            return False
        prop = session.query(Property).filter(
            Property.name == property_name, Property.object_id == obj.id
        ).one_or_none()
        if not prop:
            return False
        if is_params_protected(prop.params):
            return True
        prop.params = merge_entity_params(prop.params, {"protected": True})
        session.commit()
        object_id = obj.id
    objects_storage.reload_object(object_id)
    return True


def isClassPropertyProtected(class_property: str) -> bool:
    """True, если свойство класса имеет ``params.protected``."""
    parts = _split_qualified(class_property)
    if not parts:
        return False
    class_name, property_name = parts
    with session_scope() as session:
        cls = session.query(Class).filter(Class.name == class_name).one_or_none()
        if not cls:
            return False
        prop = session.query(Property).filter(
            Property.name == property_name, Property.class_id == cls.id
        ).one_or_none()
        if not prop:
            return False
        return is_params_protected(prop.params)


def markClassPropertyProtected(class_property: str) -> bool:
    """Выставляет ``params.protected`` у свойства класса (``Class.prop``)."""
    parts = _split_qualified(class_property)
    if not parts:
        return False
    class_name, property_name = parts
    with session_scope() as session:
        cls = session.query(Class).filter(Class.name == class_name).one_or_none()
        if not cls:
            return False
        prop = session.query(Property).filter(
            Property.name == property_name, Property.class_id == cls.id
        ).one_or_none()
        if not prop:
            return False
        if is_params_protected(prop.params):
            return True
        prop.params = merge_entity_params(prop.params, {"protected": True})
        session.commit()
        class_id = cls.id
    objects_storage.reload_objects_by_class(class_id)
    return True


def isObjectMethodProtected(object_method: str) -> bool:
    """True, если метод объекта имеет ``params.protected``."""
    parts = _split_qualified(object_method)
    if not parts:
        return False
    object_name, method_name = parts
    with session_scope() as session:
        obj = session.query(Object).filter(Object.name == object_name).one_or_none()
        if not obj:
            return False
        method = session.query(Method).filter(
            Method.name == method_name, Method.object_id == obj.id
        ).one_or_none()
        if not method:
            return False
        return is_params_protected(method.params)


def markObjectMethodProtected(object_method: str) -> bool:
    """Выставляет ``params.protected`` у метода объекта (``Obj.method``)."""
    parts = _split_qualified(object_method)
    if not parts:
        return False
    object_name, method_name = parts
    with session_scope() as session:
        obj = session.query(Object).filter(Object.name == object_name).one_or_none()
        if not obj:
            return False
        method = session.query(Method).filter(
            Method.name == method_name, Method.object_id == obj.id
        ).one_or_none()
        if not method:
            return False
        if is_params_protected(method.params):
            return True
        method.params = merge_entity_params(method.params, {"protected": True})
        session.commit()
        object_id = obj.id
    objects_storage.reload_object(object_id)
    return True


def isClassMethodProtected(class_method: str) -> bool:
    """True, если метод класса имеет ``params.protected``."""
    parts = _split_qualified(class_method)
    if not parts:
        return False
    class_name, method_name = parts
    with session_scope() as session:
        cls = session.query(Class).filter(Class.name == class_name).one_or_none()
        if not cls:
            return False
        method = session.query(Method).filter(
            Method.name == method_name, Method.class_id == cls.id
        ).one_or_none()
        if not method:
            return False
        return is_params_protected(method.params)


def markClassMethodProtected(class_method: str) -> bool:
    """Выставляет ``params.protected`` у метода класса (``Class.method``)."""
    parts = _split_qualified(class_method)
    if not parts:
        return False
    class_name, method_name = parts
    with session_scope() as session:
        cls = session.query(Class).filter(Class.name == class_name).one_or_none()
        if not cls:
            return False
        method = session.query(Method).filter(
            Method.name == method_name, Method.class_id == cls.id
        ).one_or_none()
        if not method:
            return False
        if is_params_protected(method.params):
            return True
        method.params = merge_entity_params(method.params, {"protected": True})
        session.commit()
        class_id = cls.id
    objects_storage.reload_objects_by_class(class_id)
    return True
