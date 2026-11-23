from flask import request
from flask_restx import Namespace, Resource, fields
from app.api.models import (
    model_error_message,
    model_object_summary,
    model_success,
    wrap_result,
)
from app.api.decorators import api_key_required
from app.api.property_helpers import collect_object_property_values
from app.authentication.handlers import handle_user_required
from app.core.lib.entity_params import is_entity_visible, parse_bool_flag
from app.core.main.ObjectsStorage import objects_storage

objects_ns = Namespace(
    name="objects",
    description="Object metadata, property values and listings",
    validate=True,
)

object_summary = objects_ns.model('ObjectSummary', model_object_summary)

response_object = objects_ns.model(
    'ResultObject',
    wrap_result(fields.Nested(object_summary, description='Object summary')),
)
response_object_data = objects_ns.model(
    'ResultObjectData',
    wrap_result(fields.Raw(
        description='Object with name, description and property name→value map',
    )),
)
response_name_map = objects_ns.model(
    'ResultNameMap',
    wrap_result(fields.Raw(
        description='Map of object name to description string',
    )),
)
response_details_map = objects_ns.model(
    'ResultObjectsDetails',
    wrap_result(fields.Raw(
        description='Map of object name to ObjectSummary (description/properties/methods)',
    )),
)
response_by_class = objects_ns.model(
    'ResultObjectsByClass',
    wrap_result(fields.Raw(
        description='Map of object name to {name, description, properties values}',
    )),
)
response_success = objects_ns.model('Success', model_success)
response_not_found = objects_ns.model('ErrorMessage', model_error_message)


def _visibility_flags():
    """Флаги advanced/hidden из query."""
    return (
        parse_bool_flag(request.args.get("advanced")),
        parse_bool_flag(request.args.get("hidden")),
    )


@objects_ns.route("/<object_name>", endpoint="object")
class GetObject(Resource):
    @api_key_required
    @handle_user_required
    @objects_ns.doc(security="apikey", description="Get object properties and methods descriptions")
    @objects_ns.param("advanced", "Include advanced properties/methods (params.advanced). Default: false", _in="query")
    @objects_ns.param("hidden", "Include hidden properties/methods (params.hidden). Default: false", _in="query")
    @objects_ns.response(200, "Retrieved object.", response_object)
    @objects_ns.response(404, 'Not Found', response_not_found)
    def get(self, object_name):
        '''
        Get object description with property and method name maps.
        '''
        include_advanced, include_hidden = _visibility_flags()
        item = objects_storage.getObjectByName(object_name)
        if item:
            obj = {}
            obj['description'] = item.description
            obj['properties'] = {}
            for key, prop in item.properties.items():
                if not is_entity_visible(
                    getattr(prop, "params", None),
                    include_advanced=include_advanced,
                    include_hidden=include_hidden,
                ):
                    continue
                obj['properties'][key] = prop.description
            obj['methods'] = {}
            for key, m in item.methods.items():
                if not is_entity_visible(
                    getattr(m, "params", None),
                    include_advanced=include_advanced,
                    include_hidden=include_hidden,
                ):
                    continue
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
    @objects_ns.doc(security="apikey", description="Get object property values")
    @objects_ns.param("advanced", "Include advanced properties (params.advanced). Default: false", _in="query")
    @objects_ns.param("hidden", "Include hidden properties (params.hidden). Default: false", _in="query")
    @objects_ns.response(200, "Retrieved object data.", response_object_data)
    @objects_ns.response(404, 'Not Found', response_not_found)
    def get(self, object_name):
        '''
        Get object name, description and current property values.
        '''
        include_advanced, include_hidden = _visibility_flags()
        item = objects_storage.getObjectByName(object_name)
        if item:
            obj = {}
            obj['name'] = object_name
            obj['description'] = item.description
            obj.update(collect_object_property_values(
                item,
                include_advanced=include_advanced,
                include_hidden=include_hidden,
            ))
            return {
                'success': True,
                'result': obj}, 200
        return {
            'success': False,
            'message': 'Object not found'}, 404

    @api_key_required
    @handle_user_required
    @objects_ns.doc(security="apikey", description="Set multiple object properties from JSON body")
    @objects_ns.expect(objects_ns.model('ObjectDataSetBody', {
        'property_name': fields.Raw(description='Arbitrary property name → value pairs'),
    }), validate=False)
    @objects_ns.response(200, "Properties updated.", response_success)
    @objects_ns.response(404, 'Not Found', response_not_found)
    def post(self, object_name):
        '''
        Set object properties from JSON body (keys = property names).
        '''
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
    @objects_ns.doc(security="apikey", description="List all objects as name→description map")
    @objects_ns.param("advanced", "Include advanced objects (params.advanced). Default: false", _in="query")
    @objects_ns.param("hidden", "Include hidden objects (params.hidden). Default: false", _in="query")
    @objects_ns.response(200, "Retrieved objects dict.", response_name_map)
    def get(self):
        """
        Get dictionary of objects description.
        """
        include_advanced, include_hidden = _visibility_flags()
        result = {}
        for key, obj in objects_storage.items():
            if not is_entity_visible(
                getattr(obj, "params", None),
                include_advanced=include_advanced,
                include_hidden=include_hidden,
            ):
                continue
            result[key] = obj.description
        return {'success': True,
                'result': result}, 200

@objects_ns.route("/list/details", endpoint="objects_list_details")
class ObjectListDetails(Resource):
    """Handles HTTP requests to URL: /objects/details."""
    @api_key_required
    @handle_user_required
    @objects_ns.doc(security="apikey", description="List objects with property and method descriptions")
    @objects_ns.param("advanced", "Include advanced objects/properties/methods (params.advanced). Default: false", _in="query")
    @objects_ns.param("hidden", "Include hidden objects/properties/methods (params.hidden). Default: false", _in="query")
    @objects_ns.response(200, "Retrieved objects dict.", response_details_map)
    def get(self):
        """
        Get dictionary objects with properties and methods descriptions.

        By default excludes entities with ``params.advanced`` or ``params.hidden``.
        Pass ``advanced=1`` / ``hidden=1`` to include them.
        """
        include_advanced, include_hidden = _visibility_flags()
        result = {}
        for name, item in objects_storage.items():
            if not is_entity_visible(
                getattr(item, "params", None),
                include_advanced=include_advanced,
                include_hidden=include_hidden,
            ):
                continue
            obj = {}
            obj['description'] = item.description
            obj['properties'] = {"description": "Description object"}
            for key, prop in item.properties.items():
                if not is_entity_visible(
                    getattr(prop, "params", None),
                    include_advanced=include_advanced,
                    include_hidden=include_hidden,
                ):
                    continue
                obj['properties'][key] = prop.description
            obj['methods'] = {}
            for key, m in item.methods.items():
                if not is_entity_visible(
                    getattr(m, "params", None),
                    include_advanced=include_advanced,
                    include_hidden=include_hidden,
                ):
                    continue
                obj['methods'][key] = m.description
            result[name] = obj
        return {'success': True,
                'result': result}, 200

@objects_ns.route("/class/<class_name>", endpoint="objects_list_by_class")
class ObjectByClass(Resource):
    """Handles HTTP requests to URL: /class/<class_name>."""
    @api_key_required
    @handle_user_required
    @objects_ns.doc(security="apikey", description="List objects of a class with property values")
    @objects_ns.param("advanced", "Include advanced objects/properties (params.advanced). Default: false", _in="query")
    @objects_ns.param("hidden", "Include hidden objects/properties (params.hidden). Default: false", _in="query")
    @objects_ns.response(200, "Retrieved objects dict.", response_by_class)
    def get(self, class_name):
        """
        Get dictionary of objects of the given class with property values.
        """
        include_advanced, include_hidden = _visibility_flags()
        result = {}
        from app.core.lib.object import getObjectsByClass
        objs = getObjectsByClass(class_name)

        for item in objs:
            if not is_entity_visible(
                getattr(item, "params", None),
                include_advanced=include_advanced,
                include_hidden=include_hidden,
            ):
                continue
            obj = {}
            obj['name'] = item.name
            obj['description'] = item.description
            obj['properties'] = collect_object_property_values(
                item,
                include_advanced=include_advanced,
                include_hidden=include_hidden,
            )
            result[item.name] = obj
        return {'success': True,
                'result': result}, 200
