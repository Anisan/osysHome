import datetime
import json
import os
from flask import request, current_app
from flask_restx import Namespace, Resource
from app.api.decorators import api_key_required
from app.authentication.handlers import handle_user_required, handle_admin_required
from app.api.models import model_404, model_result
from app.core.models.Plugins import Plugin
from app.database import row2dict, session_scope, get_now_to_utc
from app.core.main.PluginsHelper import plugins
from app.core.lib.object import getProperty
from app.extensions import cache
from app.configuration import Config

# Импорт библиотеки для парсинга Markdown
_markdown_lib = None
_markdown_module = None
try:
    import markdown
    _markdown_lib = 'markdown'
    _markdown_module = markdown
except ImportError:
    try:
        import markdown2
        _markdown_lib = 'markdown2'
        _markdown_module = markdown2
    except ImportError:
        _markdown_lib = None
        _markdown_module = None

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
                        if "cycle" in item["actions"]:
                            item["updatedCycle"] = module["instance"].dtUpdated
                    else:
                        item["installed"] = False
                else:
                    item["title"] = item["name"]

            updated = getProperty("SystemVar.upgraded")
            if updated is None or updated is False:
                updated = get_now_to_utc() - datetime.timedelta(10000)
            osysHome = {
                "title": "osysHome",
                "name": "osysHome",
                "description":"Object System smartHome",
                "topic":["core","smarthome"],
                "need_restart": getProperty("SystemVar.NeedRestart"),
                "branch": getProperty("SystemVar.core_branch"),
                "update": getProperty("SystemVar.update"),
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

@plugins_ns.route("/<path:plugin_name>/settings")
class PluginSettings(Resource):
    @api_key_required
    @handle_admin_required
    @plugins_ns.doc(security="apikey")
    def get(self,plugin_name):
        """
        Get settings for plugin.
        """
        with session_scope() as session:
            module = session.query(Plugin).filter(Plugin.name == plugin_name).one_or_none()
            if module:
                config = {}
                if module.config:
                    config = json.loads(module.config)
                config['title'] = module.title
                config['category'] = module.category
                config['hidden'] = module.hidden
                config['active'] = module.active
                config['url'] = module.url
                config['branch'] = module.branch
                return config, 200
            else:
                return {"message": f"Plugin '{plugin_name}' not found", "status": "error"}, 404

    @api_key_required
    @handle_admin_required
    @plugins_ns.doc(security="apikey")
    def post(self,plugin_name):
        """
        Update settings for plugin.
        """
        with session_scope() as session:
            module = session.query(Plugin).filter(Plugin.name == plugin_name).one_or_none()
            if module:
                config = request.get_json() 
                if "title" in config:
                    module.title = config['title']
                    del config['title']
                if "category" in config:
                    module.category = config['category']
                    del config['category']
                if "hidden" in config:
                    module.hidden = config['hidden']
                    del config['hidden']
                if "active" in config:
                    module.active = config['active']
                    del config['active']
                if "url" in config:
                    module.url = config['url']
                    del config['url']
                if "branch" in config:
                    module.branch = config['branch']
                    del config['branch']

                module.config = json.dumps(config)

                session.commit()
                cache.delete('sidebar')
                if plugin_name in plugins:
                    plugins[plugin_name]["instance"].loadConfig()

                return {"message": f"Settings for plugin '{plugin_name}' updated", "status": "ok"}, 200
            else:
                return {"message": f"Plugin '{plugin_name}' not found", "status": "error"}, 404

@plugins_ns.route("/<path:plugin_name>/readme")
class GetPluginReadme(Resource):
    @api_key_required
    @handle_user_required
    @plugins_ns.doc(security="apikey")
    def get(self, plugin_name):
        """
        Get README file content for plugin as HTML (parsed from Markdown).
        """
        # Определяем язык из запроса или используем язык по умолчанию
        lang = request.args.get('lang', current_app.config.get('DEFAULT_LANGUAGE', 'en'))
        
        # Путь к папке плагина
        plugin_path = os.path.join(Config.PLUGINS_FOLDER, plugin_name)
        
        # Проверяем наличие README файла для выбранного языка
        readme_files = []
        if lang != 'en':
            # Сначала пробуем локализованную версию
            readme_files.append(os.path.join(plugin_path, f"README.{lang}.md"))
        # Затем пробуем базовый README.md
        readme_files.append(os.path.join(plugin_path, "README.md"))
        
        # Ищем первый существующий файл
        readme_content = None
        for readme_path in readme_files:
            if os.path.exists(readme_path) and os.path.isfile(readme_path):
                try:
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        readme_content = f.read()
                    readme_path_used = readme_path
                    break
                except Exception as e:
                    return {"message": f"Error reading README file: {str(e)}", "status": "error"}, 500
        
        if readme_content is None:
            return {"message": f"README file not found for plugin '{plugin_name}'", "status": "error"}, 404
        
        # Конвертируем Markdown в HTML
        html_content = readme_content
        if _markdown_lib and _markdown_module:
            try:
                if _markdown_lib == 'markdown':
                    # Используем библиотеку markdown (стандартная)
                    md = _markdown_module.Markdown(extensions=['fenced_code', 'tables', 'toc', 'codehilite'])
                    html_content = md.convert(readme_content)
                elif _markdown_lib == 'markdown2':
                    # Используем markdown2 (через pdoc)
                    html_content = _markdown_module.markdown(readme_content, extras=['fenced-code-blocks', 'tables', 'header-ids'])
                
                # Преобразуем относительные пути к изображениям в абсолютные
                # Обрабатываем пути вида static/image.png или ./static/image.png
                import re
                from urllib.parse import urlparse
                
                def fix_image_path(match):
                    img_tag = match.group(0)
                    src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag)
                    if src_match:
                        src_path = src_match.group(1)
                        # Проверяем, что это относительный путь (не начинается с http://, https://, /, data:)
                        parsed = urlparse(src_path)
                        if not parsed.scheme and not src_path.startswith('/') and not src_path.startswith('data:'):
                            # Преобразуем в абсолютный путь относительно плагина
                            # Убираем ./ если есть
                            clean_path = src_path.lstrip('./')
                            # Формируем абсолютный путь: /plugin_name/static/image.png
                            absolute_path = f"/{plugin_name}/{clean_path}"
                            # Заменяем путь в теге img
                            new_img_tag = re.sub(r'src=["\'][^"\']+["\']', f'src="{absolute_path}"', img_tag)
                            return new_img_tag
                    return img_tag
                
                # Находим и заменяем все теги img с относительными путями
                html_content = re.sub(r'<img[^>]+src=["\'][^"\']+["\'][^>]*>', fix_image_path, html_content)
                
            except Exception as e:
                # В случае ошибки парсинга возвращаем исходный текст как HTML
                from html import escape
                html_content = f"<pre>{escape(readme_content)}</pre>"
                # Логируем ошибку, но не прерываем выполнение
                from app.logging_config import getLogger
                logger = getLogger("main")
                logger.warning("Error parsing Markdown for %s: %s", plugin_name, str(e))
        else:
            # Если библиотека не установлена, возвращаем как plain text в <pre>
            from html import escape
            html_content = f"<pre>{escape(readme_content)}</pre>"
        
        return {"success": True, "content": html_content, "lang": lang, "raw": False}, 200

@plugins_ns.route("/<path:plugin_name>/readme/check")
class CheckPluginReadme(Resource):
    @api_key_required
    @handle_user_required
    @plugins_ns.doc(security="apikey")
    def get(self, plugin_name):
        """
        Check if README file exists for plugin.
        """
        plugin_path = os.path.join(Config.PLUGINS_FOLDER, plugin_name)
        readme_path = os.path.join(plugin_path, "README.md")
        
        exists = os.path.exists(readme_path) and os.path.isfile(readme_path)
        
        return {"success": True, "exists": exists}, 200
