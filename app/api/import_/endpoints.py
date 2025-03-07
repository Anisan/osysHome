
from flask import request, jsonify
from flask_restx import Namespace, Resource
import json
from app.database import db
from app.api.decorators import api_key_required
from app.authentication.handlers import handle_admin_required

from app.core.models.Clasess import Class, Object, Property, Method, Value

import_ns = Namespace(name="import",description="Import namespace",validate=True)

@import_ns.route("", endpoint="import_objects")
class ImportObjects(Resource):
    @api_key_required
    @handle_admin_required
    @import_ns.doc(security="apikey")
    @import_ns.doc(params={'file': 'The file to import'},)
    def post(self):
            file = request.files['file']
            if file.filename == '':
                return jsonify({"message": "No selected file"})
            if file and file.filename.endswith('.json'):
                try:
                    data = json.load(file)

                    for c in data['classes']:
                        cls = Class.query.filter(Class.name == c['name']).one_or_none()
                        if not cls:
                            cls = Class()
                            cls.name = c['name']
                            db.session.add(cls)
                        cls.description = c['description']
                        cls.template = c['template']
                        if c['parent']:
                            parent = Class.query.filter(Class.name == c['parent']).one_or_none()
                            cls.parent_id = parent.id
                    
                    if 'objects' in data:
                        for o in data['objects']:
                            obj = Object.query.filter(Object.name == o['name']).one_or_none()
                            if not obj:
                                obj = Object()
                                obj.name = o['name']
                                db.session.add(obj)
                            obj.description = o['description']
                            obj.template = o['template']
                            cls = Class.query.filter(Class.name == o['class']).one_or_none()
                            obj.class_id = cls.id

                    for m in data['methods']:
                        if 'class' in m:
                            cls = Class.query.filter(Class.name == m['class']).one_or_none()
                            method = Method.query.filter(Method.name == m['name'], Method.class_id == cls.id).one_or_none()
                            if not method:
                                method = Method()
                                method.name = m['name']
                                method.class_id = cls.id
                                db.session.add(method)

                        if 'object' in m:
                            obj = Object.query.filter(Object.name == m['object']).one_or_none()
                            method = Method.query.filter(Method.name == m['name'], Method.object_id == obj.id).one_or_none()
                            if not method:
                                method = Method()
                                method.name = m['name']
                                method.object_id = obj.id
                                db.session.add(method)
                        
                        method.description = m['description']
                        method.code = m['code']
                        method.call_parent = m['call_parent']

                    for p in data['properties']:
                        if 'class' in p:
                            cls = Class.query.filter(Class.name == p['class']).one_or_none()
                            property = Property.query.filter(Property.name == p['name'], Property.class_id == cls.id).one_or_none()
                            if not property:
                                property = Property()
                                property.name = p['name']
                                property.class_id = cls.id
                                db.session.add(property)

                        if 'object' in p:
                            obj = Object.query.filter(Object.name == p['object']).one_or_none()
                            property = Property.query.filter(Property.name == p['name'], Property.object_id == obj.id).one_or_none()
                            if not property:
                                property = Property()
                                property.name = p['name']
                                property.object_id = obj.id
                                db.session.add(property)
                        
                        property.description = p['description']
                        property.type = p['type']
                        property.history = p['history']

                        if p['method']:
                            method = None
                            if 'class_method' in p and p['class_method']:
                                c = Class.query.filter(Class.name == p['class_method']).one_or_none()
                                method = Method.query.filter(Method.name == p['method'], Method.class_id == c.id).one_or_none()
                            if 'object_method' in p and p['object_method']:
                                o = Object.query.filter(Object.name == p['object_method']).one_or_none()
                                method = Method.query.filter(Method.name == p['method'], Method.object_id == o.id).one_or_none()
                            if method:
                                property.method_id = method.id

                    if 'values' in data:
                        for v in data['values']:
                            obj = Object.query.filter(Object.name == v['object']).one_or_none()
                            value = Value.query.filter(Value.object_id == obj.id, Value.name == v['name']).one_or_none()
                            if not value:
                                value = Value()
                                value.name = v['name']
                                value.object_id = obj.id
                                db.session.add(value)
                        
                        value.value = v['value']
                    
                    db.session.commit()
                        
                    return jsonify({"message": "File imported successfully"})
                except json.JSONDecodeError:
                    return jsonify({"message": "Invalid JSON file"})
            else:
                return jsonify({"message": "File must be in JSON format"})

