from http import HTTPStatus
from flask import request, abort
from flask_restx import Namespace, Resource
from app.api.decorators import api_key_required, role_required
from app.core.main.ObjectsStorage import objects

props_ns = Namespace(name="property",description="Property namespace",validate=True)


@props_ns.route("/list/<object_name>", endpoint="properties_list")
class PropertiesList(Resource):
    @api_key_required
    @role_required('admin')
    @props_ns.doc(security="apikey")
    @props_ns.response(HTTPStatus.OK, "Retrieved list properties of object.")
    def get(self, object_name):
        '''
        Get properties of object.
        '''
        result = {}
        if object_name in objects:
            for key,prop in objects[object_name].properties.items():
                result[key] = prop.description
        return result
    
@props_ns.route("/get", endpoint="property_get")
class GetProperty(Resource):
    @api_key_required
    @role_required('admin')
    @props_ns.doc(security="apikey")
    @props_ns.param('object', 'Object name')
    @props_ns.param('property', 'Property name')
    def get(self):
        '''
        Get value of object property.
        '''
        result = ''
        object_name = request.args.get("object",None)
        property_name = request.args.get("property",None)
        if not object_name or not property_name:
            abort(404, 'Missing required parameters')
        if object_name in objects:
            result = objects[object_name].getProperty(property_name)
        return result

@props_ns.route("/set", endpoint="property_set")
class SetProperty(Resource):
    @api_key_required
    @role_required('admin')
    @props_ns.doc(security="apikey")
    @props_ns.param('object', 'Object name')
    @props_ns.param('property', 'Property name')
    @props_ns.param('value', 'Value')
    def get(self):
        '''
        Set value of object property.
        '''
        result = ''
        object_name = request.args.get("object",None)
        property_name = request.args.get("property",None)
        value = request.args.get("value",None)
        if not object_name or not property_name or not value:
            abort(404, 'Missing required parameters')
        if object_name in objects:
            result = objects[object_name].setProperty(property_name, value, "api")
        return result