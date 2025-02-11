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
        return {"success": True,
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
        return {"success": True}, 200

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
        return {"success": True}, 200


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
        try:
            payload = request.get_json()
            code = payload['code']
            from app.core.lib.common import runCode
            result, success = runCode(code)
            return {"success": success,
                    "result": result}, 200
        except Exception as ex:
            return {"success": False,
                    "result": ex}, 200
    

cron_task_model = utils_ns.model('CodeTextModel', {
    'method': fields.String(description='Object method', required=True),
    'crontab': fields.String(description='Crontab', required=True)
})

@utils_ns.route('/crontask')
class setCronTask(Resource):
    @api_key_required
    @role_required('admin')
    @utils_ns.expect(cron_task_model, validate=True)
    @utils_ns.doc(security="apikey")
    def post(self):
        '''
        Set cron task for method
        '''
        payload = request.get_json()
        obj = payload['method'].split(".")[0]
        method = payload['method'].split(".")[1]
        crontab = payload['crontab']

        from app.core.lib.common import addCronJob, clearScheduledJob
        clearScheduledJob(f'{obj}_{method}_periodic')
        if crontab:
            addCronJob(f'{obj}_{method}_periodic',f'callMethod("{obj}.{method}", source="Scheduler")',crontab)

        return {"success": True}, 200
