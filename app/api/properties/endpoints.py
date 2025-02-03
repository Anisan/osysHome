import datetime
from flask import request, abort
from flask_restx import Namespace, Resource, fields
from app.database import session_scope
from app.api.decorators import api_key_required, role_required
from app.api.models import model_result, model_404
from app.core.lib.object import getProperty
from app.core.main.ObjectsStorage import objects_storage

props_ns = Namespace(name="property", description="Property namespace", validate=True)

response_result = props_ns.model('Result', model_result)
response_404 = props_ns.model('Error', model_404)

@props_ns.route("/list/<object_name>", endpoint="properties_list")
class PropertiesList(Resource):
    @api_key_required
    @role_required('user')
    @props_ns.doc(security="apikey")
    @props_ns.response(200, "Retrieved list properties of object.", response_result)
    @props_ns.response(404, 'Not Found', response_404)
    def get(self, object_name):
        '''
        Get properties of object.
        '''
        result = {}
        obj = objects_storage.getObjectByName(object_name)
        if obj is None:
            return {"success": False,
                    "msg": "Object not found."}, 404
        for key,prop in obj.properties.items():
            result[key] = prop.description
        return {"success": True,
                "result": result}, 200

@props_ns.route("/get", endpoint="property_get")
class GetProperty(Resource):
    @api_key_required
    @role_required('user')
    @props_ns.doc(security="apikey")
    @props_ns.param('object', 'Object name')
    @props_ns.param('property', 'Property name')
    @props_ns.response(200, "Result", response_result)
    @props_ns.response(404, 'Not Found', response_404)
    def get(self, object_property):
        '''
        Get value of object property.
        '''
        result = ''
        # Если object_property передан в path, разбираем его
        if object_property:
            if '.' not in object_property:
                abort(400, 'Invalid format. Expected "object.property"')
            object_name, property_name = object_property.split('.', 1)
        else:
            # Иначе берем параметры из query string
            object_name = request.args.get("object")
            property_name = request.args.get("property")
            if not object_name or not property_name:
                abort(400, 'Missing required parameters: object and property')
        
        obj = objects_storage.getObjectByName(object_name)
        if obj is None:
            return {"success": False,
                    "msg": "Object not found."}, 404
        if property_name == "description":
            result = obj.description
        elif property_name == "template":
            result = obj.template
        else:
            result = obj.getProperty(property_name)
        return {"success": True,
                "result": result}, 200
 
    @api_key_required
    @role_required('user')
    @props_ns.doc(security="apikey")
    @props_ns.expect(props_ns.model('PropertiesList', {
        'properties': fields.List(fields.String, required=True, description='List of properties to get')
    }))
    @props_ns.response(200, "Result", response_result)
    @props_ns.response(404, 'Not Found', response_404)
    def post(self):
        '''
        Get values of multiple object properties.
        '''
        data = request.json
        properties = data.get('properties', [])

        result = {}
        for object_property in properties:
            object_name, property_name = object_property.split('.', 1)
            obj = objects_storage.getObjectByName(object_name)
            if obj:
                data = {}
                if property_name in obj.properties:
                    prop = obj.properties[property_name]
                    data['value'] = prop.value
                    data['source'] = prop.source
                    data['changed'] = prop.changed
                    result[object_property] = data
        return {"success": True,
                "result": result}, 200

@props_ns.route("/<path:object_property>", endpoint="property_get_with_path")
class PropertyWithPath(Resource):
    @api_key_required
    @role_required('user')
    @props_ns.doc(security="apikey")
    @props_ns.param('object_property', 'Object and property name in format "object.property"', _in='path')
    @props_ns.response(200, "Result", response_result)
    @props_ns.response(404, 'Not Found', response_404)
    def get(self, object_property):
        '''
        Get value of object property.
        '''
        result = ''
        # Если object_property передан в path, разбираем его
        if object_property:
            if '.' not in object_property:
                abort(400, 'Invalid format. Expected "object.property"')
            object_name, property_name = object_property.split('.', 1)
        else:
            abort(400, 'Missing required parameters: object.property')
        
        obj = objects_storage.getObjectByName(object_name)
        if obj is None:
            return {"success": False,
                    "msg": "Object not found."}, 404
        if property_name == "description":
            result = obj.description
        elif property_name == "template":
            result = obj.template
        else:
            result = {}
            if property_name in obj.properties:
                prop = obj.properties[property_name]
                result['value'] = prop.value
                result['source'] = prop.source
                result['changed'] = prop.changed
        return {"success": True,
                "result": result}, 200

    @api_key_required
    @role_required('user')
    @props_ns.doc(security="apikey")
    def post(self, object_property):
        '''
        Set value of object property.
        '''
        if object_property:
            if '.' not in object_property:
                abort(400, 'Invalid format. Expected "object.property"')
            object_name, payload = object_property.split('.', 1)
        else:
            abort(400, 'Missing required parameters: object.property')
        item = objects_storage.getObjectByName(object_name)
        if item:
            payload = request.get_json()
            value = payload['data']
            source = payload.get('source', 'api')
            item.setProperty(payload,value,source)
            return {'success': True}, 200
        return {
            'success': False,
            'message': 'Object not found'}, 404

@props_ns.route("/set", endpoint="property_set")
class SetProperty(Resource):
    @api_key_required
    @role_required('user')
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
        obj = objects_storage.getObjectByName(object_name)
        if obj is None:
            return {"success": False,
                    "msg": "Object not found."}, 404
        result = obj.setProperty(property_name, value, "api")
        return {"success": True,
                "result": result}, 200

@props_ns.route("/history", endpoint="property_history")
class GetHistory(Resource):
    @api_key_required
    @role_required('user')
    @props_ns.doc(security="apikey")
    @props_ns.doc(params={
        'object': {'description': 'The object name (source)', 'type': 'string', 'required': True},
        'property': {'description': 'The property name (source)', 'type': 'string', 'required': True},
        'dt_begin': {'description': 'The start date and time for filtering (format: YYYY-MM-DDTHH:MM:SS)', 'type': 'string', 'required': False},
        'dt_end': {'description': 'The end date and time for filtering (format: YYYY-MM-DDTHH:MM:SS)', 'type': 'string', 'required': False},
        'limit': {'description': 'The limit on the number of results', 'type': 'integer', 'required': False},
        'order_desc': {'description': 'Whether to order results in descending order', 'type': 'boolean', 'required': False},
    })
    @props_ns.response(200, "Result", response_result)
    @props_ns.response(404, 'Not Found', response_404)
    def get(self):
        '''
        Get history value of object property.
        '''
        result = None
        object_name = request.args.get("object",None)
        property_name = request.args.get("property",None)
        if not object_name or not property_name:
            abort(404, 'Missing required parameters')
        obj = objects_storage.getObjectByName(object_name)
        if obj is None:
            return {"success": False,
                    "msg": "Object not found."}, 404

        dt_begin_str = request.args.get('dt_begin')
        dt_end_str = request.args.get('dt_end')
        limit = request.args.get('limit', type=int)
        order_desc_str = request.args.get('order_desc', default='false').lower()

        order_desc = order_desc_str == 'true'

        dt_begin = datetime.datetime.fromisoformat(dt_begin_str) if dt_begin_str else None
        dt_end = datetime.datetime.fromisoformat(dt_end_str) if dt_end_str else None

        result = obj.getHistory(property_name, dt_begin, dt_end, limit, order_desc)

        return {"success": True,
                "result": result}, 200

    @props_ns.doc(params={
        'id': {'description': 'The unique identifier of the history entry', 'type': 'integer', 'required': True},
    })
    def delete(self):
        '''
        Delete a history entry.
        '''
        id = request.args.get('id', type=int)
        with session_scope() as session:
            from app.core.models.Clasess import History
            if History.delete_by_id(session, id):
                return {"success": True, 'message': 'Entry deleted successfully'}, 200
        return {"success": False, 'message': 'Entry not found'}, 404

@props_ns.route("/history/aggregate")
class GetAggregateHistory(Resource):
    @api_key_required
    @role_required('user')
    @props_ns.doc(security="apikey")
    @props_ns.doc(params={
        'object': {'description': 'The object name (source)', 'type': 'string', 'required': True},
        'property': {'description': 'The property name (source)', 'type': 'string', 'required': True},
        'dt_begin': {'description': 'The start date and time for filtering (format: YYYY-MM-DDTHH:MM:SS)', 'type': 'string', 'required': False},
        'dt_end': {'description': 'The end date and time for filtering (format: YYYY-MM-DDTHH:MM:SS)', 'type': 'string', 'required': False},
    })
    @props_ns.response(200, "Result", response_result)
    @props_ns.response(404, 'Not Found', response_404)
    def get(self):
        '''
        Get history aggregate value of object property.
        '''
        result = None
        object_name = request.args.get("object",None)
        property_name = request.args.get("property",None)
        if not object_name or not property_name:
            abort(404, 'Missing required parameters')
        obj = objects_storage.getObjectByName(object_name)
        if obj is None:
            return {"success": False,
                    "msg": "Object not found."}, 404

        dt_begin_str = request.args.get('dt_begin')
        dt_end_str = request.args.get('dt_end')

        dt_begin = datetime.datetime.fromisoformat(dt_begin_str) if dt_begin_str else None
        dt_end = datetime.datetime.fromisoformat(dt_begin_str) if dt_end_str else None

        result = obj.getHistoryAggregate(property_name, dt_begin, dt_end)

        return {"success": True,
                "result": result}, 200
