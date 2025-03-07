from flask import request
from flask_restx import Namespace, Resource
from app.api.models import model_result, model_404
from app.api.decorators import api_key_required
from app.authentication.handlers import handle_user_required, handle_admin_required
from app.core.main.ObjectsStorage import objects_storage

objects_ns = Namespace(name="objects",description="Objects namespace",validate=True)

response_result = objects_ns.model('Result', model_result)
response_404 = objects_ns.model('Error', model_404)

@objects_ns.route("/<object_name>", endpoint="object")
class GetObject(Resource):
    @api_key_required
    @handle_user_required
    @objects_ns.doc(security="apikey")
    @objects_ns.response(200, "Retrieved object.", response_result)
    @objects_ns.response(404, 'Not Found', response_404)
    def get(self, object_name):
        '''
        Get object.
        '''
        item = objects_storage.getObjectByName(object_name)
        if item:
            obj = {}
            obj['description'] = item.description
            obj['properties'] = {}
            for key,prop in item.properties.items():
                obj['properties'][key] = prop.description
            obj['methods'] = {}
            for key,m in item.methods.items():
                obj['methods'][key] = m.description
            return {
                'success': True,
                'result': obj}, 200
        return {
            'success': False,
            'message': 'Object not found'}, 404
    
@objects_ns.route("/data/<object_name>", endpoint="object_data")
class GetObjectData(Resource):
    @api_key_required
    @handle_user_required
    @objects_ns.doc(security="apikey")
    @objects_ns.response(200, "Retrieved object data.", response_result)
    @objects_ns.response(404, 'Not Found', response_404)
    def get(self, object_name):
        '''
        Get object.
        '''
        item = objects_storage.getObjectByName(object_name)
        if item:
            obj = {}
            obj['name'] = object_name
            obj['description'] = item.description
            for key,prop in item.properties.items():
                obj[key] = prop.value
            return {
                'success': True,
                'result': obj}, 200
        return {
            'success': False,
            'message': 'Object not found'}, 404
    @api_key_required
    @handle_user_required
    @objects_ns.doc(security="apikey")
    def post(self, object_name):
        item = objects_storage.getObjectByName(object_name)
        if item:
            payload = request.get_json()
            for key,value in payload.items():
                item.setProperty(key,value,'api')
            return {'success': True}, 200
        return {
            'success': False,
            'message': 'Object not found'}, 404
    
@objects_ns.route("/list", endpoint="objects_list")
class ObjectList(Resource):
    """Handles HTTP requests to URL: /objects."""
    @api_key_required
    @handle_user_required
    @objects_ns.doc(security="apikey")
    @objects_ns.response(200, "Retrieved objects dict.", response_result)
    def get(self):
        """
        Get dictionary of objects description.
        """
        result = {}
        objects_storage.preload_objects()
        for key,obj in objects_storage.items():
            result[key] = obj.description
        return {'success': True,
                'result': result}, 200
    
@objects_ns.route("/list/details", endpoint="objects_list_details")
class ObjectListDetails(Resource):
    """Handles HTTP requests to URL: /objects/details."""
    @api_key_required
    @handle_user_required
    @objects_ns.doc(security="apikey")
    @objects_ns.response(200, "Retrieved objects dict.", response_result)
    def get(self):
        """
        Get dictionary objects with properties and methods descriptions
        """
        result = {}
        objects_storage.preload_objects()
        for name,item in objects_storage.items():
            obj = {}
            obj['description'] = item.description
            obj['properties'] = {}
            for key,prop in item.properties.items():
                obj['properties'][key] = prop.description
            obj['methods'] = {}
            for key,m in item.methods.items():
                obj['methods'][key] = m.description
            result[name] = obj
        return {'success': True,
                'result': result}, 200
    
@objects_ns.route("/class/<class_name>", endpoint="objects_list_by_class")
class ObjectByClass(Resource):
    """Handles HTTP requests to URL: /class/<class_name>."""
    @api_key_required
    @handle_user_required
    @objects_ns.doc(security="apikey")
    @objects_ns.response(200, "Retrieved objects dict.", response_result)
    def get(self, class_name):
        """
        Get dictionary objects with properties
        """
        result = {}
        from app.core.lib.object import getObjectsByClass
        objs = getObjectsByClass(class_name)
        
        for item in objs:
            obj = {}
            obj['name'] = item.name
            obj['description'] = item.description
            obj['properties'] = {}
            for key,prop in item.properties.items():
                obj['properties'][key] = prop.value
            result[item.name] = obj
        return {'success': True,
                'result': result}, 200