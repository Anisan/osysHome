
from flask import request, jsonify, Response
from flask_restx import Namespace, Resource
import json
from app.database import db
from app.api.decorators import api_key_required, role_required
from app.core.models.Clasess import Class, Object, Property, Method, Value
from app.logging_config import getLogger

_logger = getLogger("api")

def getClassWithParents(class_id):
    classes = []
    cls = Class.get_by_id(class_id)
    if cls.parent_id:
        parent = getClassWithParents(cls.parent_id)
        classes += parent
    classes.append(cls)
    return classes

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

export_ns = Namespace(name="export",description="Export namespace",validate=True)

@export_ns.route("/class/<class_id>", endpoint="export_class")
class ExportClass(Resource):
    @api_key_required
    @role_required('admin')
    @export_ns.doc(security="apikey")
    def get(self, class_id):
        '''
        Export class
        '''
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


@export_ns.route("/class_all/<class_id>", endpoint="export_all_class")
class ExportAllClass(Resource):
    @api_key_required
    @role_required('admin')
    @export_ns.doc(security="apikey")
    def get(self, class_id):
        '''
        Export class
        '''
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

@export_ns.route("/object/<object_id>", endpoint="export_object")
class ExportObject(Resource):
    @api_key_required
    @role_required('admin')
    @export_ns.doc(security="apikey")
    def get(self, object_id):
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
