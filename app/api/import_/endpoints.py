
from collections import defaultdict

from flask import request, jsonify, Response, stream_with_context
from flask_restx import Namespace, Resource
import json
from app.database import db
from app.core.main.ObjectsStorage import objects_storage
from app.api.decorators import api_key_required
from app.authentication.handlers import handle_admin_required
from app.core.models.Clasess import Class, Object, Property, Method, Value
from app.core.lib.object_tree import invalidate_objects_tree_cache
from app.logging_config import getLogger

_logger = getLogger("api")

import_ns = Namespace(name="import", description="Import namespace", validate=True)


def _emit(event):
    return json.dumps(event, ensure_ascii=False) + "\n"


def _import_status(imported, skipped=False, updated=False):
    if imported:
        return "updated" if updated else "imported"
    if skipped:
        return "skipped"
    return "skipped"


def _index_import_data(data):
    classes = data.get("classes") or []
    class_names = {c["name"] for c in classes}
    class_by_name = {c["name"]: c for c in classes}
    children_by_parent = defaultdict(list)
    roots = []

    for c in classes:
        parent = c.get("parent")
        if parent and parent in class_by_name:
            children_by_parent[parent].append(c["name"])
        else:
            roots.append(c["name"])

    objects_by_class = defaultdict(list)
    standalone_objects = []
    for o in data.get("objects") or []:
        cls_name = o.get("class")
        if cls_name and cls_name in class_names:
            objects_by_class[cls_name].append(o)
        else:
            standalone_objects.append(o)

    properties_by_class = defaultdict(list)
    properties_by_object = defaultdict(list)
    for p in data.get("properties") or []:
        if "class" in p:
            properties_by_class[p["class"]].append(p)
        elif "object" in p:
            properties_by_object[p["object"]].append(p)

    methods_by_class = defaultdict(list)
    methods_by_object = defaultdict(list)
    for m in data.get("methods") or []:
        if "class" in m:
            methods_by_class[m["class"]].append(m)
        elif "object" in m:
            methods_by_object[m["object"]].append(m)

    values_by_object = defaultdict(list)
    for v in data.get("values") or []:
        values_by_object[v["object"]].append(v)

    return {
        "class_by_name": class_by_name,
        "roots": roots,
        "children_by_parent": children_by_parent,
        "objects_by_class": objects_by_class,
        "standalone_objects": standalone_objects,
        "properties_by_class": properties_by_class,
        "properties_by_object": properties_by_object,
        "methods_by_class": methods_by_class,
        "methods_by_object": methods_by_object,
        "values_by_object": values_by_object,
        "values": data.get("values") or [],
    }


def _import_class_record(class_data, rewrite, add_classes):
    cls = Class.query.filter(Class.name == class_data["name"]).one_or_none()
    existed = cls is not None
    update_class = rewrite and cls
    imported = False
    if add_classes and not cls:
        cls = Class()
        cls.name = class_data["name"]
        db.session.add(cls)
        update_class = True
    if update_class:
        cls.description = class_data["description"]
        cls.template = class_data["template"]
        if class_data.get("parent"):
            parent = Class.query.filter(Class.name == class_data["parent"]).one_or_none()
            if parent:
                cls.parent_id = parent.id
        imported = True
    return imported, existed


def _import_object_record(object_data, rewrite, add_objects):
    obj = Object.query.filter(Object.name == object_data["name"]).one_or_none()
    existed = obj is not None
    update_object = rewrite and obj
    imported = False
    if add_objects and not obj:
        obj = Object()
        obj.name = object_data["name"]
        db.session.add(obj)
        update_object = True
    if update_object:
        obj.description = object_data["description"]
        obj.template = object_data["template"]
        if object_data.get("class"):
            cls = Class.query.filter(Class.name == object_data["class"]).one_or_none()
            if cls:
                obj.class_id = cls.id
        imported = True
    return imported, existed


def _import_class_property(property_data, rewrite):
    cls = Class.query.filter(Class.name == property_data["class"]).one_or_none()
    if not cls:
        return False

    property = Property.query.filter(
        Property.name == property_data["name"],
        Property.class_id == cls.id,
    ).one_or_none()
    update_property = rewrite and property
    if not property:
        property = Property()
        property.name = property_data["name"]
        property.class_id = cls.id
        db.session.add(property)
        update_property = True

    if not update_property:
        return False

    property.description = property_data["description"]
    property.type = property_data["type"]
    property.history = property_data["history"]
    if "params" in property_data:
        property.params = property_data["params"]

    if property_data.get("method"):
        method = None
        if property_data.get("class_method"):
            c = Class.query.filter(Class.name == property_data["class_method"]).one_or_none()
            if c:
                method = Method.query.filter(
                    Method.name == property_data["method"],
                    Method.class_id == c.id,
                ).one_or_none()
        if property_data.get("object_method"):
            o = Object.query.filter(Object.name == property_data["object_method"]).one_or_none()
            if o:
                method = Method.query.filter(
                    Method.name == property_data["method"],
                    Method.object_id == o.id,
                ).one_or_none()
        if method:
            property.method_id = method.id

    return True


def _import_object_property(property_data, rewrite):
    obj = Object.query.filter(Object.name == property_data["object"]).one_or_none()
    if not obj:
        return False

    property = Property.query.filter(
        Property.name == property_data["name"],
        Property.object_id == obj.id,
    ).one_or_none()
    update_property = rewrite and property
    if not property:
        property = Property()
        property.name = property_data["name"]
        property.object_id = obj.id
        db.session.add(property)
        update_property = True

    if not update_property:
        return False

    property.description = property_data["description"]
    property.type = property_data["type"]
    property.history = property_data["history"]
    if "params" in property_data:
        property.params = property_data["params"]

    if property_data.get("method"):
        method = None
        if property_data.get("class_method"):
            c = Class.query.filter(Class.name == property_data["class_method"]).one_or_none()
            if c:
                method = Method.query.filter(
                    Method.name == property_data["method"],
                    Method.class_id == c.id,
                ).one_or_none()
        if property_data.get("object_method"):
            o = Object.query.filter(Object.name == property_data["object_method"]).one_or_none()
            if o:
                method = Method.query.filter(
                    Method.name == property_data["method"],
                    Method.object_id == o.id,
                ).one_or_none()
        if method:
            property.method_id = method.id

    return True


def _import_class_method(method_data, rewrite, add_classes):
    if not add_classes:
        return False

    cls = Class.query.filter(Class.name == method_data["class"]).one_or_none()
    if not cls:
        return False

    method = Method.query.filter(
        Method.name == method_data["name"],
        Method.class_id == cls.id,
    ).one_or_none()
    update_method = rewrite and method
    if not method:
        method = Method()
        method.name = method_data["name"]
        method.class_id = cls.id
        db.session.add(method)
        update_method = True

    if not update_method:
        return False

    method.description = method_data["description"]
    method.code = method_data["code"]
    method.call_parent = method_data["call_parent"]
    return True


def _import_object_method(method_data, rewrite, add_objects):
    if not add_objects:
        return False

    obj = Object.query.filter(Object.name == method_data["object"]).one_or_none()
    if not obj:
        return False

    method = Method.query.filter(
        Method.name == method_data["name"],
        Method.object_id == obj.id,
    ).one_or_none()
    update_method = rewrite and method
    if not method:
        method = Method()
        method.name = method_data["name"]
        method.object_id = obj.id
        db.session.add(method)
        update_method = True

    if not update_method:
        return False

    method.description = method_data["description"]
    method.code = method_data["code"]
    method.call_parent = method_data["call_parent"]
    return True


def _import_value_record(value_data, rewrite):
    obj = Object.query.filter(Object.name == value_data["object"]).one_or_none()
    if not obj:
        return False

    value = Value.query.filter(
        Value.object_id == obj.id,
        Value.name == value_data["name"],
    ).one_or_none()
    update_value = rewrite and value
    if not value:
        value = Value()
        value.name = value_data["name"]
        value.object_id = obj.id
        db.session.add(value)
        update_value = True

    if not update_value:
        return False

    value.value = value_data["value"]
    return True


def _entity_stats_event(entity_type, name, stats, class_name=None):
    event = {
        "event": "entity_stats",
        "type": entity_type,
        "name": name,
        "properties": stats["properties"],
        "methods": stats["methods"],
    }
    if class_name is not None:
        event["class"] = class_name
    return event


def _import_events(data, rewrite, add_classes, add_objects):
    """Yield progress events while importing parsed JSON in tree order."""

    idx = _index_import_data(data)
    classes = data.get("classes") or []
    objects = data.get("objects") or []
    properties = data.get("properties") or []
    methods = data.get("methods") or []
    values = idx["values"]

    total = len(classes) + len(objects) + len(properties) + len(methods) + len(values)
    yield {"event": "start", "total": total}

    def process_class(class_name):
        class_data = idx["class_by_name"].get(class_name)
        if not class_data:
            return

        stats = {"properties": 0, "methods": 0}
        yield {
            "event": "item",
            "type": "class",
            "name": class_name,
            "status": "processing",
        }

        imported, existed = _import_class_record(class_data, rewrite, add_classes)

        for property_data in idx["properties_by_class"][class_name]:
            yield {
                "event": "subitem",
                "entity_type": "class",
                "entity_name": class_name,
                "subitem_type": "property",
                "subitem_name": property_data["name"],
            }
            if _import_class_property(property_data, rewrite):
                stats["properties"] += 1
                yield _entity_stats_event("class", class_name, stats)

        for method_data in idx["methods_by_class"][class_name]:
            yield {
                "event": "subitem",
                "entity_type": "class",
                "entity_name": class_name,
                "subitem_type": "method",
                "subitem_name": method_data["name"],
            }
            if _import_class_method(method_data, rewrite, add_classes):
                stats["methods"] += 1
                yield _entity_stats_event("class", class_name, stats)

        yield {
            "event": "item",
            "type": "class",
            "name": class_name,
            "status": _import_status(imported, skipped=not imported, updated=existed),
        }

        for object_data in idx["objects_by_class"][class_name]:
            yield from process_object(object_data, class_name)

        for child_name in idx["children_by_parent"][class_name]:
            yield from process_class(child_name)

    def process_object(object_data, class_name):
        object_name = object_data["name"]
        stats = {"properties": 0, "methods": 0}

        yield {
            "event": "item",
            "type": "object",
            "name": object_name,
            "class": class_name or "",
            "status": "processing",
        }

        imported, existed = _import_object_record(object_data, rewrite, add_objects)

        for property_data in idx["properties_by_object"][object_name]:
            yield {
                "event": "subitem",
                "entity_type": "object",
                "entity_name": object_name,
                "entity_class": class_name or "",
                "subitem_type": "property",
                "subitem_name": property_data["name"],
            }
            if _import_object_property(property_data, rewrite):
                stats["properties"] += 1
                yield _entity_stats_event("object", object_name, stats, class_name or "")

        for value_data in idx["values_by_object"][object_name]:
            _import_value_record(value_data, rewrite)
            yield {"event": "progress"}

        for method_data in idx["methods_by_object"][object_name]:
            yield {
                "event": "subitem",
                "entity_type": "object",
                "entity_name": object_name,
                "entity_class": class_name or "",
                "subitem_type": "method",
                "subitem_name": method_data["name"],
            }
            if _import_object_method(method_data, rewrite, add_objects):
                stats["methods"] += 1
                yield _entity_stats_event("object", object_name, stats, class_name or "")

        yield {
            "event": "item",
            "type": "object",
            "name": object_name,
            "class": class_name or "",
            "status": _import_status(imported, skipped=not imported, updated=existed),
        }

    for root_name in idx["roots"]:
        yield from process_class(root_name)

    for object_data in idx["standalone_objects"]:
        yield from process_object(object_data, "")

    db.session.commit()
    objects_storage.clear()
    invalidate_objects_tree_cache()


@import_ns.route("", endpoint="import_objects")
class ImportObjects(Resource):
    @api_key_required
    @handle_admin_required
    @import_ns.doc(security="apikey")
    @import_ns.doc(params={"file": "The file to import"},)
    @import_ns.param("rewrite", "Rewrite existing classes/objects")
    @import_ns.param("classes", "Add classes")
    @import_ns.param("objects", "Add objects")
    @import_ns.param("stream", "Stream progress as NDJSON")
    def post(self):
        '''
        Import classes/objects from JSON file
        '''
        import_file = request.files["file"]
        if import_file.filename == "":
            return jsonify({"success": False, "message": "No selected file"})
        if not (import_file and import_file.filename.endswith(".json")):
            return jsonify({"success": False, "message": "File must be in JSON format"})

        rewrite = request.args.get("rewrite", False)
        add_classes = request.args.get("classes", False)
        add_objects = request.args.get("objects", False)
        use_stream = request.args.get("stream", False)

        try:
            data = json.load(import_file)
        except Exception:
            return jsonify({"success": False, "message": "Invalid JSON file"})

        if use_stream:
            def generate():
                try:
                    for event in _import_events(data, rewrite, add_classes, add_objects):
                        yield _emit(event)
                    yield _emit({
                        "event": "done",
                        "success": True,
                        "message": "File imported successfully",
                    })
                except Exception as ex:
                    db.session.rollback()
                    _logger.exception(ex)
                    yield _emit({"event": "error", "message": "Invalid JSON file"})

            return Response(
                stream_with_context(generate()),
                mimetype="application/x-ndjson",
            )

        try:
            list(_import_events(data, rewrite, add_classes, add_objects))
            return jsonify({"success": True, "message": "File imported successfully"})
        except Exception as ex:
            db.session.rollback()
            _logger.exception(ex)
            return jsonify({"success": False, "message": "Invalid JSON file"})
