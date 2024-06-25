from http import HTTPStatus
from flask import jsonify
from flask_restx import Namespace, Resource
from app.api.decorators import api_key_required, role_required
from app.core.main.ObjectsStorage import objects

objects_ns = Namespace(name="objects",description="Objects namespace",validate=True)

@objects_ns.route("/<object_name>", endpoint="object")
class GetObject(Resource):
    @api_key_required
    @role_required('admin')
    @objects_ns.doc(security="apikey")
    @objects_ns.response(HTTPStatus.OK, "Retrieved object.")
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
            return obj
        return jsonify({'message': 'Object not found'}), HTTPStatus.NOT_FOUND
    
@objects_ns.route("/list", endpoint="objects_list")
class ObjectList(Resource):
    """Handles HTTP requests to URL: /objects."""
    @api_key_required
    @role_required('admin')
    @objects_ns.doc(security="apikey")
    @objects_ns.response(HTTPStatus.OK, "Retrieved objects dict.")
    def get(self):
        """
        Get dictionary of objects description.
        """
        result = {}
        for key,obj in objects.items():
            result[key] = obj.description
        return result
    
@objects_ns.route("/list/details", endpoint="objects_list_details")
class ObjectListDetails(Resource):
    """Handles HTTP requests to URL: /objects/details."""
    @api_key_required
    @role_required('admin')
    @objects_ns.doc(security="apikey")
    @objects_ns.response(HTTPStatus.OK, "Retrieved objects dict.")
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
        return result