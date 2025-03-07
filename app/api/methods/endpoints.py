from flask import request, abort
from flask_restx import Namespace, Resource, fields
from app.api.decorators import api_key_required
from app.authentication.handlers import handle_user_required
from app.api.models import model_result, model_404
from app.core.main.ObjectsStorage import objects_storage

methods_ns = Namespace(name="methods",description="Methods namespace",validate=True)

response_result = methods_ns.model('Result', model_result)
response_404 = methods_ns.model('Error', model_404)

@methods_ns.route("/list/<object_name>", endpoint="methods_list")
class MethodsList(Resource):
    @api_key_required
    @handle_user_required
    @methods_ns.doc(security="apikey")
    @methods_ns.response(200, "Retrieved list methods of object.", response_result)
    @methods_ns.response(404, 'Not Found', response_404)
    def get(self, object_name):
        '''
        Get methods of object.
        '''
        result = {}
        obj = objects_storage.getObjectByName(object_name)
        if obj is None:
            return {"success": False,
                    "msg": "Object not found."}, 404
        for key,m in obj.methods.items():
            result[key] = m.description
        return {"success": True,
                "result": result}, 200


response_call = methods_ns.model('ResultCallMethod', {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'args': fields.Raw(description='Request arguments'),
    'result': fields.Raw(description='Result request'),
})

@methods_ns.route("/call", endpoint="method_call")
class CallMethod(Resource):
    @api_key_required
    @handle_user_required
    @methods_ns.doc(security="apikey")
    @methods_ns.param('object', 'Object name')
    @methods_ns.param('method', 'Method name')
    @methods_ns.response(200, "Retrieved result call method.", response_call)
    @methods_ns.response(404, 'Not Found', response_404)
    def get(self):
        '''
        Call method of object.
        '''
        result = ''
        object_name = request.args.get("object",None)
        method_name = request.args.get("method",None)
        if not object_name or not method_name:
            abort(404, 'Missing required parameters')
        obj = objects_storage.getObjectByName(object_name)
        if obj is None:
            return {"success": False,
                    "msg": "Object not found."}, 404
        if method_name not in obj.methods:
            return {"success": False,
                    "msg": "Method not found."}, 404
        result = obj.callMethod(method_name,request.args, 'api')
        return {"success": True,
                "args": request.args,
                "result": result}, 200


