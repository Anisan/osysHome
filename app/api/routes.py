import json
from . import blueprint
from flask import Response, request, jsonify, render_template
from app.authentication.handlers import handle_admin_required
from app.core.models.Clasess import Class, Property, Method, Object, Value
from .utils import getClassWithParents
from app.database import db
from app.logging_config import getLogger

_logger = getLogger("api")

def getClassInfo(class_id):
    data = {}
    data['classes'] = []
    data['properties'] = []
    data['methods'] = []
    classes = getClassWithParents(class_id)
    for cls in classes:
        properties = Property.query.filter(Property.class_id == cls.id).all()
        methods = Method.query.filter(Method.class_id == cls.id).all()
        # Преобразуем объект SQLAlchemy в словарь
        class_data = {
            'name': cls.name,
            'description': cls.description,
            'template': cls.template,
            'parent': None,
        }
        if cls.parent_id:
            parent_class = Class.get_by_id(cls.parent_id)
            class_data['parent'] = parent_class.name

        # Преобразуем свойства и методы в списки словарей
        properties_data = []
        for p in properties:
            method = None
            class_method = None
            if p.method_id != None:
                method = Method.get_by_id(p.method_id)
                cl = Class.get_by_id(method.class_id)
                method = method.name
                class_method = cl.name
            properties_data.append({'name': p.name, 'description':p.description, 'history':p.history, 'type':p.type, 'class_method': class_method, 'method': method, 'class':cls.name})
        methods_data = [{'name': m.name, 'description':m.description, 'code': m.code, 'call_parent':m.call_parent, 'class':cls.name} for m in methods]

        data['classes'].append(class_data)
        data['properties'] += properties_data
        data['methods'] += methods_data
    return data

def getObjectInfo(object_id):
    data = {}
    obj = Object.get_by_id(object_id)
    properties = Property.query.filter(Property.object_id == object_id).all()
    methods = Method.query.filter(Method.object_id == object_id).all()
    values = Value.query.filter(Value.object_id == object_id).all()
    # Преобразуем объект SQLAlchemy в словарь
    object_data = {
            'name': obj.name,
            'description': obj.description,
            'template': obj.template,
            'parent': None,
    }
    parent_class = Class.get_by_id(obj.class_id)
    object_data['class'] = parent_class.name

    # Преобразуем свойства и методы в списки словарей
    properties_data = []
    for p in properties:
        prop = {'name': p.name, 'description':p.description, 'history':p.history, 'type':p.type, 'method': None, 'object':obj.name}
        if p.method_id != None:
            method = Method.get_by_id(p.method_id)
            prop['method'] = method.name
            if method.class_id:
                cl = Class.get_by_id(method.class_id)
                prop['method_class'] = cl.name
            if method.object_id:
                ob = Object.get_by_id(method.object_id)
                prop['method_object'] = ob.name
        properties_data.append(prop)
    methods_data = [{'name': m.name, 'description':m.description, 'code': m.code, 'call_parent':m.call_parent, 'object':obj.name} for m in methods]
    values_data = [{'name': v.name, 'value': v.value, 'object':obj.name} for v in values]
    data['object'] = object_data
    data['properties'] = properties_data
    data['methods'] = methods_data
    data['values'] = values_data
    return data

@blueprint.route('/api/export/class/<class_id>', methods=['GET'])
@handle_admin_required
def export_class(class_id):
    data = getClassInfo(class_id)

    cls = Class.get_by_id(class_id)

    # Сериализуем данные
    serialized_data = json.dumps(data, sort_keys=True, indent=4) 
    # Устанавливаем заголовки ответа для загрузки файла
    filename = 'class_{}.json'.format(cls.name)
    response = Response(serialized_data, content_type='application/octet-stream')
    response.headers['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
    response.headers['Expires'] = '0'

    return response

@blueprint.route('/api/export/class_all/<class_id>', methods=['GET'])
@handle_admin_required
def export_all_class(class_id):
    data = getClassInfo(class_id)

    cls = Class.get_by_id(class_id)

    objs = Object.query.filter(Object.class_id == class_id).all()

    data['objects'] = []
    data['values'] = []

    for obj in objs:
        data_object = getObjectInfo(obj.id)
        data['objects'].append(data_object['object'])
        data['methods']+=data_object['methods']
        data['properties']+=data_object['properties']
        data['values'] += data_object['values']

    # Сериализуем данные
    serialized_data = json.dumps(data, sort_keys=True, indent=4) 
    # Устанавливаем заголовки ответа для загрузки файла
    filename = 'all_class_{}.json'.format(cls.name)
    response = Response(serialized_data, content_type='application/octet-stream')
    response.headers['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
    response.headers['Expires'] = '0'

    return response

@blueprint.route('/api/export/object/<object_id>', methods=['GET'])
@handle_admin_required
def export_object(object_id):
    obj = Object.get_by_id(object_id)
    data = getClassInfo(obj.class_id)

    data['objects'] = []
    data['values'] = []

    data_object = getObjectInfo(obj.id)
    data['objects'].append(data_object['object'])
    data['methods']+=data_object['methods']
    data['properties']+=data_object['properties']
    data['values'] += data_object['values']

    # Сериализуем данные
    serialized_data = json.dumps(data, sort_keys=True, indent=4) 
    # Устанавливаем заголовки ответа для загрузки файла
    filename = 'object_{}.json'.format(obj.name)
    response = Response(serialized_data, content_type='application/octet-stream')
    response.headers['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
    response.headers['Expires'] = '0'

    return response

@blueprint.route('/api/import', methods=['POST'])
@handle_admin_required
def upload_file():
    if request.method == 'POST':
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
                        method = Method.query.filter(Method.name == m['name'], Method.class_id == obj.id).one_or_none()
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
                        if 'method_class' in p and p['method_class']:
                            c = Class.query.filter(Class.name == p['method_class']).one_or_none()
                            method = Method.query.filter(Method.name == p['method'], Method.class_id == c.id).one_or_none()
                        if 'method_object' in p and p['method_object']:
                            o = Object.query.filter(Object.name == p['method_object']).one_or_none()
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
                    
                #reload objects
                from app.core.main.ObjectsStorage import init_objects
                init_objects()

                return jsonify({"message": "File imported successfully"})
            except json.JSONDecodeError:
                return jsonify({"message": "Invalid JSON file"})
        else:
            return jsonify({"message": "File must be in JSON format"})


@blueprint.route('/api/objects', methods=['GET'])
@handle_admin_required
def get_objects():
    from app.core.main.ObjectsStorage import objects
    result = {}
    for key,obj in objects.items():
        result[key] = obj.description
    return jsonify(result)

@blueprint.route('/api/properties/<object_name>', methods=['GET'])
@handle_admin_required
def get_properties(object_name):
    from app.core.main.ObjectsStorage import objects
    result = {}
    if object_name in objects:
        for key,prop in objects[object_name].properties.items():
            result[key] = prop.description
    return jsonify(result)

@blueprint.route('/api/methods/<object_name>', methods=['GET'])
@handle_admin_required
def get_methods(object_name):
    from app.core.main.ObjectsStorage import objects
    result = {}
    if object_name in objects:
        for key,m in objects[object_name].methods.items():
            result[key] = m.description
    return jsonify(result)

@blueprint.route('/api/readnotify/<id>', methods=['GET'])
@handle_admin_required
def read_notify(id):
    from app.core.lib.common import readNotify
    readNotify(id)
    return "ok"

@blueprint.route('/api/search', methods=['GET'])
@handle_admin_required
def global_search():
    result = []
    query = request.args.get("query",None)
    from app.core.main.PluginsHelper import plugins
    for _ , plugin in plugins.items():
        if "search" in plugin["instance"].actions:
            try:
                res = plugin["instance"].search(query)
                result += res
            except Exception as ex:
                _logger.exception(ex)
                name = plugin["name"]
                result.append({"url":"Logs", "title":f'{ex}', "tags":[{"name":name,"color":"danger"}]}) 

    render = render_template("search_result.html", result=result)

    return render

