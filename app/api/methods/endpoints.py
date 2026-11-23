from flask import request
import json
from flask_restx import Namespace, Resource, fields
from app.api.decorators import api_key_required
from app.authentication.handlers import handle_user_required
from app.api.models import model_404, model_method_call_result, wrap_result
from app.core.lib.entity_params import is_entity_visible, parse_bool_flag
from app.core.main.ObjectsStorage import objects_storage

methods_ns = Namespace(
    name="methods",
    description="Object methods listing and invocation",
    validate=True,
)

response_list = methods_ns.model(
    'ResultMethodsList',
    wrap_result(fields.Raw(description='Map of method name to description')),
)
response_404 = methods_ns.model('Error', model_404)
response_call = methods_ns.model('ResultCallMethod', model_method_call_result)


@methods_ns.route("/list/<object_name>", endpoint="methods_list")
class MethodsList(Resource):
    @api_key_required
    @handle_user_required
    @methods_ns.doc(security="apikey", description="List method name→description for an object")
    @methods_ns.param("advanced", "Include advanced methods (params.advanced). Default: false", _in="query")
    @methods_ns.param("hidden", "Include hidden methods (params.hidden). Default: false", _in="query")
    @methods_ns.response(200, "Retrieved list methods of object.", response_list)
    @methods_ns.response(404, 'Not Found', response_404)
    def get(self, object_name):
        '''
        Get methods of object (name → description map).
        '''
        include_advanced = parse_bool_flag(request.args.get("advanced"))
        include_hidden = parse_bool_flag(request.args.get("hidden"))
        result = {}
        obj = objects_storage.getObjectByName(object_name)
        if obj is None:
            return {"success": False,
                    "msg": "Object not found."}, 404
        for key, m in obj.methods.items():
            if not is_entity_visible(
                getattr(m, "params", None),
                include_advanced=include_advanced,
                include_hidden=include_hidden,
            ):
                continue
            result[key] = m.description
        return {"success": True,
                "result": result}, 200


@methods_ns.route("/call", endpoint="method_call")
class CallMethod(Resource):
    @api_key_required
    @handle_user_required
    @methods_ns.doc(security="apikey", description="Call object method; args from query string")
    @methods_ns.param('object', 'Object name')
    @methods_ns.param('method', 'Method name')
    @methods_ns.param('result', 'Type of result (txt, json)')
    @methods_ns.response(200, "Retrieved result call method.", response_call)
    @methods_ns.response(404, 'Not Found', response_404)
    def get(self):
        '''
        Call method of object (arguments from query string).
        '''
        result = ''
        object_name = request.args.get("object",None)
        method_name = request.args.get("method",None)
        type_result = request.args.get("result",'')
        if not object_name or not method_name:
            return {"success": False,
                    "msg": "Missing required parameters"}, 404
        obj = objects_storage.getObjectByName(object_name)
        if obj is None:
            return {"success": False,
                    "msg": "Object not found."}, 404
        if method_name not in obj.methods:
            return {"success": False,
                    "msg": "Method not found."}, 404
        result = obj.callMethod(method_name,request.args, 'api')

        if type_result == 'json':
            try:
                result = json.loads(result)
            except Exception as ex:  # noqa
                pass

        return {"success": True,
                "args": request.args,
                "result": result}, 200

    @api_key_required
    @handle_user_required
    @methods_ns.doc(security="apikey", description="Call object method; request object passed to method")
    @methods_ns.param('object', 'Object name')
    @methods_ns.param('method', 'Method name')
    @methods_ns.param('result', 'Type of result (txt, json)')
    @methods_ns.response(200, "Retrieved result call method.", response_call)
    @methods_ns.response(404, 'Not Found', response_404)
    def post(self):
        '''
        Call method of object (full request passed as params).
        '''
        result = ''
        object_name = request.args.get("object",None)
        method_name = request.args.get("method",None)
        type_result = request.args.get("result",None)
        if not object_name or not method_name:
            return {"success": False,
                    "msg": "Missing required parameters"}, 404
        obj = objects_storage.getObjectByName(object_name)
        if obj is None:
            return {"success": False,
                    "msg": "Object not found."}, 404
        if method_name not in obj.methods:
            return {"success": False,
                    "msg": "Method not found."}, 404
        result = obj.callMethod(method_name, request, 'api')

        if type_result == 'json':
            try:
                result = result.strip()
                result = json.loads(result)
            except Exception as ex:  # noqa
                pass

        return {"success": True,
                "args": request.args,
                "result": result}, 200
