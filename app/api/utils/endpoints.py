from flask import request, render_template
from flask_restx import Namespace, Resource, fields
from app.api.decorators import api_key_required, role_required
from app.logging_config import getLogger

_logger = getLogger("api")

utils_ns = Namespace(name="utils",description="Utilites namespace",validate=True)

@utils_ns.route('/search')
class GlobalSearch(Resource):
    @api_key_required
    @role_required('admin')
    @utils_ns.doc(security="apikey")
    @utils_ns.param('query', 'A query string parameter')
    def get(self):
        '''
        Global search
        '''
        result = []
        query = request.args.get("query",None)
        from app.core.main.PluginsHelper import plugins
        for _ , plugin in plugins.items():
            if "search" in plugin["instance"].actions:
                try:
                    res = plugin["instance"].search(query)
                    result += res
                except Exception as ex:
                    _logger.exception(ex)
                    name = plugin["name"]
                    result.append({"url":"Logs", "title":f'{ex}', "tags":[{"name":name,"color":"danger"}]}) 

        render = render_template("search_result.html", result=result)
        return {"success" : True,
                "result":render}, 200
    
@utils_ns.route('/readnotify/<id>')
class ReadNotify(Resource):
    @api_key_required
    @role_required('admin')
    @utils_ns.doc(security="apikey")
    def get(self, id):
        '''
        Mark read notify
        '''
        from app.core.lib.common import readNotify
        readNotify(id)
        return {"success" : True}, 200
    
@utils_ns.route('/readnotify/all')
class ReadNotifyAll(Resource):
    @api_key_required
    @role_required('admin')
    @utils_ns.doc(security="apikey")
    @utils_ns.param('source', 'Source notify')
    def get(self):
        '''
        Mark read all notify for source
        '''
        source = request.args.get("source",None)
        if not source:
            return {"success": False,
                    "msg": "Need source"}, 404
        from app.core.lib.common import readNotifyAll
        readNotifyAll(source)
        return {"success" : True}, 200
        
run_model = utils_ns.model('CodeTextModel', {
    'code': fields.String(description='Python code', required=True)
})

@utils_ns.route('/run')
class RunCode(Resource):
    @api_key_required
    @role_required('admin')
    @utils_ns.expect(run_model, validate=True)
    @utils_ns.doc(security="apikey")
    def post(self):
        '''
        Run code
        '''
        payload = request.get_json()
        code = payload['code']
        from app.core.lib.common import runCode
        success, result = runCode(code)
        return {"success" : success,
                "result": result}, 200