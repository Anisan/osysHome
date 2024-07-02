from flask import request, abort
from flask_restx import Namespace, Resource
from app.api.decorators import api_key_required, role_required
from app.api.models import model_result, model_404
from app.core.main.ObjectsStorage import objects

props_ns = Namespace(name="property",description="Property namespace",validate=True)

response_result = props_ns.model('Result', model_result)
response_404 = props_ns.model('Error', model_404)

@props_ns.route("/list/<object_name>", endpoint="properties_list")
class PropertiesList(Resource):
    @api_key_required
    @role_required('admin')
    @props_ns.doc(security="apikey")
    @props_ns.response(200, "Retrieved list properties of object.", response_result)
    @props_ns.response(404, 'Not Found', response_404)
    def get(self, object_name):
        '''
        Get properties of object.
        '''
        result = {}
        if object_name not in objects:
            return {"success": False,
                    "msg": "Object not found."}, 404
        for key,prop in objects[object_name].properties.items():
            result[key] = prop.description
        return {"success" : True,
                "result" : result}, 200
    
@props_ns.route("/get", endpoint="property_get")
class GetProperty(Resource):
    @api_key_required
    @role_required('admin')
    @props_ns.doc(security="apikey")
    @props_ns.param('object', 'Object name')
    @props_ns.param('property', 'Property name')
    @props_ns.response(200, "Result", response_result)
    @props_ns.response(404, 'Not Found', response_404)
    def get(self):
        '''
        Get value of object property.
        '''
        result = ''
        object_name = request.args.get("object",None)
        property_name = request.args.get("property",None)
        if not object_name or not property_name:
            abort(404, 'Missing required parameters')
        if object_name not in objects:
            return {"success": False,
                    "msg": "Object not found."}, 404
        result = objects[object_name].getProperty(property_name)
        return {"success" : True,
                "result" : result}, 200

@props_ns.route("/set", endpoint="property_set")
class SetProperty(Resource):
    @api_key_required
    @role_required('admin')
    @props_ns.doc(security="apikey")
    @props_ns.param('object', 'Object name')
    @props_ns.param('property', 'Property name')
    @props_ns.param('value', 'Value')
    @props_ns.response(200, "Result", response_result)
    @props_ns.response(404, 'Not Found', response_404)
    def get(self):
        '''
        Set value of object property.
        '''
        object_name = request.args.get("object",None)
        property_name = request.args.get("property",None)
        value = request.args.get("value",None)
        if not object_name or not property_name or not value:
            abort(404, 'Missing required parameters')
        if object_name not in objects:
            return {"success": False,
                    "msg": "Object not found."}, 404
        result = objects[object_name].setProperty(property_name, value, "api")
        return {"success" : True,
                "result" : result}, 200