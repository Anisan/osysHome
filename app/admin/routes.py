from flask import render_template, send_from_directory
import subprocess
from . import blueprint
from app.authentication.handlers import handle_admin_required
from settings import Config

@blueprint.route("/admin")
@handle_admin_required
def control_panel():
    content = {}
    return render_template("control_panel.html", **content)

# Маршрут для отображения файлов документации
@blueprint.route('/docs/<path:filename>')
def docs_file(filename):
    return send_from_directory(Config.DOCS_DIR, filename)


@blueprint.route('/restart')
@handle_admin_required
def restart():
    """Маршрут для перезапуска приложения через systemd"""
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', 'smh'], check=True)
        return "osysHome is restarting...", 200
    except subprocess.CalledProcessError as e:
        return f"Error: {e}", 500
    