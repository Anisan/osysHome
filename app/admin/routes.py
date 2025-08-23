from flask import render_template, send_from_directory, current_app, session
from . import blueprint
from settings import Config
from app.logging_config import getLogger
from app.authentication.handlers import handle_user_required, handle_editor_required
from app.core.lib.common import getModulesByAction

_logger = getLogger("main")

@blueprint.route("/admin")
@handle_editor_required
def control_panel():
    widgets = {}
    modules = getModulesByAction("widget")
    for plugin in modules:
        if plugin.config.get('hide_widget',False):
            continue
        try:
            widgets[plugin.name] = plugin.widget()
        except Exception as ex:
            _logger.exception(ex)

    content = {"widgets":widgets}
    return render_template("control_panel.html", **content)

@blueprint.route("/pages")
@handle_user_required
def pages_panel():
    modules = getModulesByAction("page")
    content = {"modules":modules}
    return render_template("pages_panel.html", **content)

# Маршрут для отображения файлов документации
@blueprint.route('/docs/<path:filename>')
@handle_user_required
def docs_file(filename):
    return send_from_directory(Config.DOCS_DIR, filename)

# About
@blueprint.route("/about")
@handle_user_required
def about():
    return render_template("about.html", LANGUAGES=current_app.config['LANGUAGES'])

@blueprint.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in current_app.translations:
        session['lang'] = lang
    return 'Ok'
