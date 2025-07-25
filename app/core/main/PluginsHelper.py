import os
import importlib.util
from app.database import model_exists, row2dict, get_now_to_utc
from app.core.models.Plugins import Plugin, Notify
from app.extensions import cache
from app.core.lib.constants import CategoryNotify

from app.logging_config import getLogger
_logger = getLogger('plugin_helper')

plugins = {}

def registerPlugins(app):
    _logger.debug("Register plugins")
    # Папка, в которой находятся плагины
    plugin_folder = app.config.get("PLUGINS_FOLDER", "plugins")

    # Загрузка плагинов
    for folder_name in os.listdir(plugin_folder):
        plugin_path = os.path.join(plugin_folder, folder_name)
        if os.path.isdir(plugin_path):
            plugin_files = [f for f in os.listdir(plugin_path) if f == "__init__.py"]
            plugin_name = os.path.basename(plugin_path)
            _logger.debug(f"Register plugin  {plugin_name}")
            try:
                for plugin_file in plugin_files:
                    plugin_file_path = os.path.join(plugin_path, plugin_file)
                    spec = importlib.util.spec_from_file_location(
                        plugin_name, plugin_file_path
                    )
                    plugin_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(plugin_module)
                    plugin_class = getattr(plugin_module, plugin_name, None)
                    if plugin_class and model_exists(Plugin):
                        with app.app_context():
                            plugin_db = Plugin.query.filter(
                                Plugin.name == plugin_name
                            ).one_or_none()
                            if plugin_db is None:
                                plugin_db = Plugin()
                                plugin_db.name = plugin_name
                                plugin_db.updated = get_now_to_utc()
                                plugin_db.save()
                            if plugin_db.active:
                                plugin_instance = plugin_class(
                                    app
                                )  # Создаем экземпляр плагина
                                plugins[plugin_name] = {
                                    "name": plugin_name,
                                    "instance": plugin_instance,
                                    "file_path": plugin_file_path,
                                }
            except Exception as ex:
                _logger.exception(ex)

    # Регистрируем контекстный процессор
    @app.context_processor
    def inject_sidebar():
        def get_sidebar():
            # cashed plugins for sidebar
            sidebar = cache.get('sidebar')
            if sidebar is None or len(sidebar) == 0:
                sidebar = []
                for _, plugin in plugins.items():
                    plugin_rec = Plugin.query.filter(
                        Plugin.name == plugin["instance"].name
                    ).one_or_none()
                    if not plugin_rec:
                        sidebar.append(
                            {
                                "name": plugin["instance"].name,
                                "title": plugin["instance"].title,
                                "custom_title": None,
                                "route": "/admin/" + plugin["name"],
                                "category": plugin["instance"].category,
                                "custom_category": None,
                            }
                        )
                    else:
                        if plugin_rec.hidden == 0:
                            sidebar.append(
                                {
                                    "name": plugin["instance"].name,
                                    "title": plugin["instance"].title,
                                    "custom_title": plugin_rec.title,
                                    "route": "/admin/" + plugin["name"],
                                    "category": plugin["instance"].category,
                                    "custom_category": plugin_rec.category,
                                }
                            )
                sidebar.sort(key=lambda x: x["title"], reverse=False)
                cache.set('sidebar', sidebar, timeout=0)
            # get notify
            from app.database import db
            from sqlalchemy import text
            database_dialect = db.engine.dialect.name
            notifies = []
            if database_dialect == 'mysql':
                notifies = db.session.execute(text("SELECT source, sum(count) FROM notify WHERE `read` = 0 GROUP BY source"))
            else:
                notifies = db.session.execute(text('SELECT source, sum(count) FROM notify WHERE read IS false GROUP BY source'))

            for n in notifies:
                for item in sidebar:
                    if n[0] == item['name']:
                        item['notify'] = n[1]

            groups = {}
            from app import safe_translate
                
            for item in sidebar:
                if item["custom_title"]:
                    item['title'] = item["custom_title"]
                else:
                    title = safe_translate(item['title'])
                    if title:
                        item['title'] = title
                category = item["category"]
                if item['custom_category']:
                    category = item["custom_category"]
                else:
                    #   _('System')
                    #   _('App')
                    #   _('Devices')
                    #   _('Automation')
                    #   _('Communication')
                    #   _('Network')
                    category = safe_translate(category)
                if category not in groups:
                    groups[category] = []
                groups[category].append(item)
            return groups

        def getListNotify(source):
            data = Notify.query.filter(Notify.read == False, Notify.source == source).all()
            res = []
            for rec in data:
                item = row2dict(rec)
                item['color'] = "danger"
                if rec.category == CategoryNotify.Debug:
                    item['color'] = "secondary"
                elif rec.category == CategoryNotify.Warning:
                    item['color'] = "warning"
                elif rec.category == CategoryNotify.Info:
                    item['color'] = "success"
                res.append(item)
            return res

        return {
            'sidebar': get_sidebar,
            'list_notify': getListNotify,
        }


# Запуск плагинов
def start_plugins():
    _logger.info("Starting plugins cycle...")
    for _, plugin_info in plugins.items():
        plugin = plugin_info["instance"]
        plugin.initialization()
        if 'cycle' in plugin.actions:
            plugin.start_cycle()


def stop_plugins():
    _logger.info("Stoping plugins cycle...")
    for _, plugin_info in plugins.items():
        plugin = plugin_info["instance"]
        if 'cycle' in plugin.actions:
            plugin.stop_cycle()
