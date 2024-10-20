import datetime
from flask import request, abort
from flask_restx import Namespace, Resource
from app.database import session_scope
from app.api.decorators import api_key_required, role_required
from app.api.models import model_result, model_404
from app.core.main.ObjectsStorage import objects

props_ns = Namespace(name="property", description="Property namespace", validate=True)

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
        return {"success": True,
                "result": result}, 200

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
        if property_name == "description":
            result = objects[object_name].description
        elif property_name == "template":
            result = objects[object_name].template
        else:
            result = objects[object_name].getProperty(property_name)
        return {"success": True,
                "result": result}, 200

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
        return {"success": True,
                "result": result}, 200

@props_ns.route("/history", endpoint="property_history")
class GetHistory(Resource):
    @api_key_required
    @role_required('admin')
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
        if object_name not in objects:
            return {"success": False,
                    "msg": "Object not found."}, 404

        dt_begin_str = request.args.get('dt_begin')
        dt_end_str = request.args.get('dt_end')
        limit = request.args.get('limit', type=int)
        order_desc_str = request.args.get('order_desc', default='false').lower()

        order_desc = order_desc_str == 'true'

        dt_begin = datetime.datetime.fromisoformat(dt_begin_str) if dt_begin_str else None
        dt_end = datetime.datetime.fromisoformat(dt_end_str) if dt_end_str else None

        result = objects[object_name].getHistory(property_name, dt_begin, dt_end, limit, order_desc)

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
    @role_required('admin')
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
        if object_name not in objects:
            return {"success": False,
                    "msg": "Object not found."}, 404

        dt_begin_str = request.args.get('dt_begin')
        dt_end_str = request.args.get('dt_end')

        dt_begin = datetime.datetime.fromisoformat(dt_begin_str) if dt_begin_str else None
        dt_end = datetime.datetime.fromisoformat(dt_begin_str) if dt_end_str else None

        result = objects[object_name].getHistoryAggregate(property_name, dt_begin, dt_end)

        return {"success": True,
                "result": result}, 200
