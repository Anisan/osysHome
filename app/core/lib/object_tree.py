"""Shared structural cache for the classes/objects tree (admin UI and tools)."""
from collections import defaultdict
from threading import Lock

from app.core.models.Clasess import Class, Object


_TREE_CACHE = {}
_TREE_CACHE_LOCK = Lock()


def _copy_items(items):
    return [item.copy() for item in items]


def _sort_items_by_name(items):
    items.sort(key=lambda item: (item.get("name") or "").lower())


def _build_tree_payload(include_hidden=False):
    class_query = Class.query
    if not include_hidden:
        class_query = class_query.filter(Class.name.notlike(r'\_%', escape='\\'))
    all_classes = class_query.order_by(Class.name).all()

    class_nodes = {
        item.id: {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "children_count": 0,
            "objects_count": 0,
        }
        for item in all_classes
    }

    children_by_parent = defaultdict(list)
    for item in all_classes:
        children_by_parent[item.parent_id].append(class_nodes[item.id])

    obj_query = Object.query
    if not include_hidden:
        obj_query = obj_query.filter(Object.name.notlike(r'\_%', escape='\\'))
    all_objects = obj_query.order_by(Object.name).all()

    objects_by_class = defaultdict(list)
    standalone_objects = []
    for obj in all_objects:
        obj_dict = {
            "id": obj.id,
            "name": obj.name,
            "description": obj.description,
        }
        if obj.class_id is None:
            standalone_objects.append(obj_dict)
        elif obj.class_id in class_nodes:
            objects_by_class[obj.class_id].append(obj_dict)

    for parent_id, children in children_by_parent.items():
        _sort_items_by_name(children)
        if parent_id in class_nodes:
            class_nodes[parent_id]["children_count"] = len(children)

    for class_id, objects in objects_by_class.items():
        _sort_items_by_name(objects)
        if class_id in class_nodes:
            class_nodes[class_id]["objects_count"] = len(objects)

    root_classes = _copy_items(children_by_parent.get(None, []))
    _sort_items_by_name(root_classes)
    _sort_items_by_name(standalone_objects)

    return {
        "root_classes": root_classes,
        "standalone_objects": _copy_items(standalone_objects),
        "children_by_parent": {
            parent_id: _copy_items(children)
            for parent_id, children in children_by_parent.items()
        },
        "objects_by_class": {
            class_id: _copy_items(objects)
            for class_id, objects in objects_by_class.items()
        },
        "classes_by_id": {
            class_id: class_info.copy()
            for class_id, class_info in class_nodes.items()
        },
    }


def get_objects_tree_payload(include_hidden=False):
    cache_key = "all" if include_hidden else "public"
    with _TREE_CACHE_LOCK:
        payload = _TREE_CACHE.get(cache_key)
        if payload is None:
            payload = _build_tree_payload(include_hidden=include_hidden)
            _TREE_CACHE[cache_key] = payload

    return {
        "root_classes": _copy_items(payload["root_classes"]),
        "standalone_objects": _copy_items(payload["standalone_objects"]),
        "children_by_parent": {
            parent_id: _copy_items(children)
            for parent_id, children in payload["children_by_parent"].items()
        },
        "objects_by_class": {
            class_id: _copy_items(objects)
            for class_id, objects in payload["objects_by_class"].items()
        },
        "classes_by_id": {
            class_id: class_info.copy()
            for class_id, class_info in payload["classes_by_id"].items()
        },
    }


def invalidate_objects_tree_cache():
    with _TREE_CACHE_LOCK:
        _TREE_CACHE.clear()
