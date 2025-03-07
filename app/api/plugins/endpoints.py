import datetime
from flask import request
from flask_restx import Namespace, Resource, fields
from app.api.decorators import api_key_required
from app.authentication.handlers import handle_user_required, handle_admin_required
from app.api.models import model_404, model_result
from app.core.models.Plugins import Plugin
from app.database import row2dict, session_scope
from app.core.main.PluginsHelper import plugins
from app.core.lib.object import getProperty

plugins_ns = Namespace(name="plugins", description="Plugins namespace", validate=True)

response_result = plugins_ns.model("Result", model_result)
response_404 = plugins_ns.model("Error", model_404)

@plugins_ns.route("/")
class GetPlugins(Resource):
    @api_key_required
    @handle_user_required
    @plugins_ns.doc(security="apikey")
    @plugins_ns.response(200, "List plugins", response_result)
    def get(self):
        """
        Get plugins
        """
        with session_scope() as session:
            ps = session.query(Plugin).order_by(Plugin.name).all()
            result = [row2dict(plugin) for plugin in ps]
            for item in result:
                if item["active"]:
                    if item["name"] in plugins:
                        module = plugins[item['name']]
                        item["installed"] = True
                        if not item['title']:
                            item["title"] = module["instance"].title
                        if not item['category']:
                            item["category"] = module["instance"].category
                        item["description"] = module["instance"].description
                        item["version"] = module["instance"].version
                        item["actions"] = module["instance"].actions
                        item["author"] = module["instance"].author
                        item["alive"] = module["instance"].is_alive()
                        item['new'] = False
                        if "cycle" in item["actions"]:
                            item["updatedCycle"] = module["instance"].dtUpdated
                    else:
                        item["installed"] = False
                else:
                    item["title"] = item["name"]

            updated = getProperty("SystemVar.upgraded")
            if updated is None or updated is False:
                updated = datetime.datetime.now() - datetime.timedelta(10000)
            osysHome = {
                "title": "osysHome",
                "name": "osysHome",
                "description":"Object System smartHome",
                "topic":["core","smarthome"],
                "new": False,
                "need_restart": getProperty("SystemVar.NeedRestart"),
                "author":"Eraser",
                "updated": updated,
                "url":"https://github.com/Anisan/osysHome",
            }
            return {"success": True, "result": result, "osysHome":osysHome}, 200
        
@plugins_ns.route("/<path:plugin_name>")
class GetPluginInfo(Resource):
    @api_key_required
    @handle_user_required
    @plugins_ns.doc(security="apikey")
    def get(self,plugin_name):
        """
        Get info plugin.
        """
        with session_scope() as session:
            ps = session.query(Plugin).filter(Plugin.name == plugin_name).one_or_none()
            if ps:
                item = row2dict(ps)
                if item["active"]:
                    if item["name"] in plugins:
                        module = plugins[item['name']]
                        item["installed"] = True
                        if not item['title']:
                            item["title"] = module["instance"].title
                        if not item['category']:
                            item["category"] = module["instance"].category
                        item["description"] = module["instance"].description
                        item["version"] = module["instance"].version
                        item["actions"] = module["instance"].actions
                        item["author"] = module["instance"].author
                        item["alive"] = module["instance"].is_alive()
                        item['new'] = False
                        if "cycle" in item["actions"]:
                            item["updatedCycle"] = module["instance"].dtUpdated
                    else:
                        item["installed"] = False
                else:
                    item["title"] = item["name"]
                return {"success": True, "result": item}, 200
            else:
                return {"message": f"Plugin '{plugin_name}' not found", "status": "error"}, 404

@plugins_ns.route("/<path:plugin_name>/start")
class StartCycle(Resource):
    @api_key_required
    @handle_admin_required
    @plugins_ns.doc(security="apikey")
    def get(self,plugin_name):
        """
        Start cycle by name plugin.
        """
        if plugin_name in plugins:
            module = plugins[plugin_name]
            if module["instance"].is_alive():
                return {"message": f"Cycle '{plugin_name}' is already running", "status": "ok"}, 200
            module["instance"].start_cycle()
            return {"message": f"Cycle '{plugin_name}' started", "status": "ok"}, 200
        else:
            return {"message": f"Plugin '{plugin_name}' not found", "status": "error"}, 404


@plugins_ns.route("/<path:plugin_name>/stop")
class StopCycle(Resource):
    @api_key_required
    @handle_admin_required
    @plugins_ns.doc(security="apikey")
    def get(self,plugin_name):
        """
        Stop cycle by name plugin.
        """
        if plugin_name in plugins:
            module = plugins[plugin_name]
            if not module["instance"].is_alive():
                return {"message": f"Cycle '{plugin_name}' is already stopped", "status": "ok"}, 200
            module["instance"].stop_cycle()
            return {"message": f"Cycle '{plugin_name}' stopped", "status": "ok"}, 200
        else:
            return {"message": f"Plugin '{plugin_name}' not found", "status": "error"}, 404

@plugins_ns.route("/<path:plugin_name>/restart")
class RestartCycle(Resource):
    @api_key_required
    @handle_admin_required
    @plugins_ns.doc(security="apikey")
    def get(self,plugin_name):
        """
        Restart cycle by name plugin.
        """
        if plugin_name in plugins:
            module = plugins[plugin_name]
            module["instance"].stop_cycle()
            module["instance"].start_cycle()
            return {"message": f"Cycle '{plugin_name}' stopped", "status": "ok"}, 200
        else:
            return {"message": f"Plugin '{plugin_name}' not found", "status": "error"}, 404
