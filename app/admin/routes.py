from flask import render_template, send_from_directory
import subprocess
import os
from . import blueprint
from settings import Config
from app.logging_config import getLogger
from app.authentication.handlers import handle_admin_required, handle_user_required
from app.core.main.PluginsHelper import plugins

_logger = getLogger("main")

@blueprint.route("/admin")
@handle_admin_required
def control_panel():
    widgets={}

    for key , plugin in plugins.items():
        if "widget" in plugin["instance"].actions:
            try:
                widgets[key] = plugin["instance"].widget()
            except Exception as ex:
                _logger.exception(ex)

    content = {"widgets":widgets}
    return render_template("control_panel.html", **content)

# Маршрут для отображения файлов документации
@blueprint.route('/docs/<path:filename>')
@handle_user_required
def docs_file(filename):
    return send_from_directory(Config.DOCS_DIR, filename)

# Маршруты для отображения файлов
@blueprint.route('/files/public/<path:filename>')
@handle_user_required
def public_file(filename):
    return send_from_directory(os.path.join(Config.FILES_DIR,"public"), filename)

@blueprint.route('/files/private/<path:filename>')
@handle_user_required
def private_file(filename):
    return send_from_directory(os.path.join(Config.FILES_DIR,"private"), filename)

@blueprint.route('/files/secure/<path:filename>')
@handle_admin_required
def secure_file(filename):
    return send_from_directory(os.path.join(Config.FILES_DIR,"secure"), filename)

#about
@blueprint.route("/about")
@handle_user_required
def about():
    return render_template("about.html")

@blueprint.route('/restart')
@handle_admin_required
def restart():
    """Маршрут для перезапуска приложения через systemd"""
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', 'smh'], check=True)
        return "osysHome is restarting...", 200
    except subprocess.CalledProcessError as e:
        return f"Error: {e}", 500
    