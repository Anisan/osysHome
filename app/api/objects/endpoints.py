from flask import request
from flask_restx import Namespace, Resource
from app.api.models import model_result, model_404
from app.api.decorators import api_key_required, role_required
from app.core.main.ObjectsStorage import objects

objects_ns = Namespace(name="objects",description="Objects namespace",validate=True)

response_result = objects_ns.model('Result', model_result)
response_404 = objects_ns.model('Error', model_404)

@objects_ns.route("/<object_name>", endpoint="object")
class GetObject(Resource):
    @api_key_required
    @role_required('admin')
    @objects_ns.doc(security="apikey")
    @objects_ns.response(200, "Retrieved object.", response_result)
    @objects_ns.response(404, 'Not Found', response_404)
    def get(self, object_name):
        '''
        Get object.
        '''
        if object_name in objects:
            obj = {}
            item = objects[object_name]
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
    @role_required('user')
    @objects_ns.doc(security="apikey")
    @objects_ns.response(200, "Retrieved object data.", response_result)
    @objects_ns.response(404, 'Not Found', response_404)
    def get(self, object_name):
        '''
        Get object.
        '''
        if object_name in objects:
            obj = {}
            item = objects[object_name]
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
    def post(self, object_name):
        if object_name in objects:
            payload = request.get_json()
            item = objects[object_name]
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
    @role_required('admin')
    @objects_ns.doc(security="apikey")
    @objects_ns.response(200, "Retrieved objects dict.", response_result)
    def get(self):
        """
        Get dictionary of objects description.
        """
        result = {}
        for key,obj in objects.items():
            result[key] = obj.description
        return {
                'success': True,
                'result':result }, 200
    
@objects_ns.route("/list/details", endpoint="objects_list_details")
class ObjectListDetails(Resource):
    """Handles HTTP requests to URL: /objects/details."""
    @api_key_required
    @role_required('admin')
    @objects_ns.doc(security="apikey")
    @objects_ns.response(200, "Retrieved objects dict.", response_result)
    def get(self):
        """
        Get dictionary objects with properties and methods descriptions
        """
        result = {}
        for name,item in objects.items():
            obj = {}
            obj['description'] = item.description
            obj['properties'] = {}
            for key,prop in item.properties.items():
                obj['properties'][key] = prop.description
            obj['methods'] = {}
            for key,m in item.methods.items():
                obj['methods'][key] = m.description
            result[name] = obj
        return {
                'success': True,
                'result':result }, 200