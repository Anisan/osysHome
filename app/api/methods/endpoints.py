from http import HTTPStatus
from flask import request, abort
from flask_restx import Namespace, Resource
from app.api.decorators import api_key_required, role_required
from app.core.main.ObjectsStorage import objects

methods_ns = Namespace(name="methods",description="Methods namespace",validate=True)


@methods_ns.route("/list/<object_name>", endpoint="methods_list")
class MethodsList(Resource):
    @api_key_required
    @role_required('admin')
    @methods_ns.doc(security="apikey")
    @methods_ns.response(HTTPStatus.OK, "Retrieved list methods of object.")
    def get(self, object_name):
        '''
        Get methods of object.
        '''
        result = {}
        if object_name in objects:
            for key,m in objects[object_name].methods.items():
                result[key] = m.description
        return result
    
@methods_ns.route("/call", endpoint="method_call")
class CallMethod(Resource):
    @api_key_required
    @role_required('admin')
    @methods_ns.doc(security="apikey")
    @methods_ns.param('object', 'Object name')
    @methods_ns.param('method', 'Method name')
    def get(self):
        '''
        Call method of object.
        '''
        result = ''
        object_name = request.args.get("object",None)
        method_name = request.args.get("method",None)
        if not object_name or not method_name:
            abort(404, 'Missing required parameters')
        if object_name in objects:
            result = objects[object_name].callMethod(method_name)
        return result