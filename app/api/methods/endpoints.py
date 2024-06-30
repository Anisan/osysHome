from http import HTTPStatus
from flask import request, abort
from flask_restx import Namespace, Resource, fields
from app.api.decorators import api_key_required, role_required
from app.core.main.ObjectsStorage import objects

methods_ns = Namespace(name="methods",description="Methods namespace",validate=True)

response_404 = methods_ns.model('Error', {
    'success': fields.Boolean(description='Indicates success of the operation', default=False),
    'msg': fields.String(description='Error message')
})

response_list = methods_ns.model('Methods', {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'methods': fields.Raw(description='Methods of the object'),
})

@methods_ns.route("/list/<object_name>", endpoint="methods_list")
class MethodsList(Resource):
    @api_key_required
    @role_required('admin')
    @methods_ns.doc(security="apikey")
    @methods_ns.response(HTTPStatus.OK, "Retrieved list methods of object.", response_list)
    @methods_ns.response(404, 'Not Found', response_404)
    def get(self, object_name):
        '''
        Get methods of object.
        '''
        result = {}
        if object_name not in objects:
            return {"success": False,
                    "msg": "Object not found."}, 404
        for key,m in objects[object_name].methods.items():
            result[key] = m.description
        return {"success" : True,
                "methods" : result}, 200

response_call = methods_ns.model('Response', {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'args': fields.Raw(description='Request arguments'),
    'data': fields.Raw(description='Resulting data'),
})

@methods_ns.route("/call", endpoint="method_call")
class CallMethod(Resource):
    @api_key_required
    @role_required('admin')
    @methods_ns.doc(security="apikey")
    @methods_ns.param('object', 'Object name')
    @methods_ns.param('method', 'Method name')
    @methods_ns.response(HTTPStatus.OK, "Retrieved result.", response_call)
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
        if object_name not in objects:
            return {"success": False,
                    "msg": "Object not found."}, 404
        if method_name not in objects[object_name].methods:
            return {"success": False,
                    "msg": "Method not found."}, 404
        result = objects[object_name].callMethod(method_name,request.args, 'api')
        return {"success" : True,
                "args" : request.args,
                "data" : result}, 200


