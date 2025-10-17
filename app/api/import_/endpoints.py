
from flask import request, jsonify
from flask_restx import Namespace, Resource
import json
from app.database import db
from app.core.main.ObjectsStorage import objects_storage
from app.api.decorators import api_key_required
from app.authentication.handlers import handle_admin_required
from app.core.models.Clasess import Class, Object, Property, Method, Value
from app.logging_config import getLogger

_logger = getLogger("api")

import_ns = Namespace(name="import",description="Import namespace",validate=True)

@import_ns.route("", endpoint="import_objects")
class ImportObjects(Resource):
    @api_key_required
    @handle_admin_required
    @import_ns.doc(security="apikey")
    @import_ns.doc(params={'file': 'The file to import'},)
    @import_ns.param('rewrite', 'Rewrite existing classes/objects')
    @import_ns.param('classes', 'Add classes')
    @import_ns.param('objects', 'Add objects')
    def post(self):
        '''
        Import classes/objects from JSON file
        '''
        import_file = request.files['file']
        if import_file.filename == '':
            return jsonify({"success": False, "message": "No selected file"})
        if import_file and import_file.filename.endswith('.json'):
            try:
                rewrite = request.args.get("rewrite", False)
                add_classes = request.args.get("classes", False)
                add_objects = request.args.get("objects", False)

                data = json.load(import_file)

                for c in data['classes']:
                    cls = Class.query.filter(Class.name == c['name']).one_or_none()
                    update_class = rewrite and cls
                    if add_classes and not cls:
                        if not cls:
                            cls = Class()
                            cls.name = c['name']
                            db.session.add(cls)
                            update_class = True
                    if update_class:
                        cls.description = c['description']
                        cls.template = c['template']
                        if c['parent']:
                            parent = Class.query.filter(Class.name == c['parent']).one_or_none()
                            if parent:
                                cls.parent_id = parent.id

                if 'objects' in data:
                    for o in data['objects']:
                        obj = Object.query.filter(Object.name == o['name']).one_or_none()
                        update_object = rewrite and obj
                        if add_objects and not obj:
                            if not obj:
                                obj = Object()
                                obj.name = o['name']
                                db.session.add(obj)
                                update_object = True
                        if update_object:
                            obj.description = o['description']
                            obj.template = o['template']
                            cls = Class.query.filter(Class.name == o['class']).one_or_none()
                            if cls:
                                obj.class_id = cls.id

                for m in data['methods']:
                    update_method = False
                    if 'class' in m and add_classes:
                        cls = Class.query.filter(Class.name == m['class']).one_or_none()
                        if cls:
                            method = Method.query.filter(Method.name == m['name'], Method.class_id == cls.id).one_or_none()
                            update_method = rewrite and method
                            if not method:
                                method = Method()
                                method.name = m['name']
                                method.class_id = cls.id
                                db.session.add(method)
                                update_method = True

                    if 'object' in m and add_objects:
                        obj = Object.query.filter(Object.name == m['object']).one_or_none()
                        if obj:
                            method = Method.query.filter(Method.name == m['name'], Method.object_id == obj.id).one_or_none()
                            update_method = rewrite and method
                            if not method:
                                method = Method()
                                method.name = m['name']
                                method.object_id = obj.id
                                db.session.add(method)
                                update_method = True

                    if update_method:
                        method.description = m['description']
                        method.code = m['code']
                        method.call_parent = m['call_parent']

                for p in data['properties']:
                    update_property = False
                    if 'class' in p:
                        cls = Class.query.filter(Class.name == p['class']).one_or_none()
                        if cls:
                            property = Property.query.filter(Property.name == p['name'], Property.class_id == cls.id).one_or_none()
                            update_property = rewrite and property
                            if not property:
                                property = Property()
                                property.name = p['name']
                                property.class_id = cls.id
                                db.session.add(property)
                                update_property = True

                    if 'object' in p:
                        obj = Object.query.filter(Object.name == p['object']).one_or_none()
                        if obj:
                            property = Property.query.filter(Property.name == p['name'], Property.object_id == obj.id).one_or_none()
                            update_property = rewrite and property
                            if not property:
                                property = Property()
                                property.name = p['name']
                                property.object_id = obj.id
                                db.session.add(property)
                                update_property = True

                    if update_property:
                        property.description = p['description']
                        property.type = p['type']
                        property.history = p['history']

                        if p['method']:
                            method = None
                            if 'class_method' in p and p['class_method']:
                                c = Class.query.filter(Class.name == p['class_method']).one_or_none()
                                if c:
                                    method = Method.query.filter(Method.name == p['method'], Method.class_id == c.id).one_or_none()
                            if 'object_method' in p and p['object_method']:
                                o = Object.query.filter(Object.name == p['object_method']).one_or_none()
                                if o:
                                    method = Method.query.filter(Method.name == p['method'], Method.object_id == o.id).one_or_none()
                            if method:
                                property.method_id = method.id

                if 'values' in data:
                    for v in data['values']:
                        update_value = False
                        obj = Object.query.filter(Object.name == v['object']).one_or_none()
                        if obj:
                            value = Value.query.filter(Value.object_id == obj.id, Value.name == v['name']).one_or_none()
                            update_value = rewrite and value
                            if not value:
                                value = Value()
                                value.name = v['name']
                                value.object_id = obj.id
                                db.session.add(value)
                                update_value = True

                            if update_value:
                                value.value = v['value']

                db.session.commit()
                objects_storage.clear()
                return jsonify({"success": True, "message": "File imported successfully"})
            except Exception as ex:
                _logger.exception(ex)
                return jsonify({"success": False, "message": "Invalid JSON file"})
        else:
            return jsonify({"success": False, "message": "File must be in JSON format"})
