import os
from app.core.migrate import perform_migrations
from flask import render_template, send_from_directory, jsonify
from . import blueprint
from settings import Config
from app.logging_config import getLogger
from app.authentication.handlers import handle_admin_required, handle_user_required
from app.core.main.PluginsHelper import plugins

_logger = getLogger("main")

# Маршруты для отображения файлов
@blueprint.route('/files/public/<path:filename>')
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
