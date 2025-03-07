""" Main module """
from importlib import import_module
from flask import Flask, request, render_template, current_app
import flask_monitoringdashboard as dashboard
from . import commands
from .exceptions import InvalidUsage
from .constants import LANGUAGES
from .extensions import db, migrate, login_manager, cors, bcrypt, babel, toolbar, cache
from .core.main.PluginsHelper import *
from app.core.utils import CustomJSONEncoder

from .logging_config import getLogger
_logger = getLogger('flask')
_logger_error_http = getLogger('404')

def createApp(config_object):
    """An application factory, as explained here:
    http://flask.pocoo.org/docs/patterns/appfactories/.

    :param config_object: The configuration object to use.
    """
    if config_object.DEBUG:
        log = getLogger('werkzeug')
    else:
        log = getLogger('werkzeug','ERROR')

    _logger.info("Init app")
    app = Flask(__name__.split('.',maxsplit=1)[0])
    app.url_map.strict_slashes = False
    app.config.from_object(config_object)
    _logger.info("DB: %s", config_object.SQLALCHEMY_DATABASE_URI)
    app.config['SQLALCHEMY_DATABASE_URI'] = config_object.SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_POOL_SIZE'] = 20
        
    app.config.update(RESTX_JSON={"cls": CustomJSONEncoder})

    if config_object.DEBUG:
        app.config['DEBUG_TB_TEMPLATE_EDITOR_ENABLED'] = True
        app.config['DEBUG_TB_PROFILER_ENABLED'] = True
        app.config['DEBUG_TB_PROFILER_DUMP_FILENAME'] = "dump.prof"
        app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] =False
        app.config['SQLALCHEMY_RECORD_QUERIES'] = True
    
    # from werkzeug.middleware.profiler import ProfilerMiddleware
    # app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[5], profile_dir='.')
   
    registerExtensions(app)
    registerBlueprints(app)
    registerErrorhandlers(app)
    registerShellcontext(app)
    registerCommands(app)
    register_plugins(app)

    if config_object.DEBUG:
        dashboard.bind(app)

    @app.context_processor
    def inject_common_data():
        return {
            'project_name': 'osysHome',
            'author': 'Eraser',
        }

    return app

def registerExtensions(app):

    from app.core.lib.object import getProperty
    # Добавляем функцию в контекст шаблона
    app.jinja_env.globals['getProperty'] = getProperty

    """Register Flask extensions."""
    bcrypt.init_app(app)
    cache.init_app(app)
    db.init_app(app)
    cors.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    toolbar.init_app(app)
    
    def locale():
        #TODO get from user language
        return request.accept_languages.best_match(LANGUAGES.keys())

    babel.init_app(app,locale_selector=locale)
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = os.path.join(basedir, 'translations')

def registerBlueprints(app):
    """Register Flask blueprints."""
    origins = app.config.get('CORS_ORIGIN_WHITELIST', '*')
    #cors.init_app(auth.views.blueprint, origins=origins)
    #cors.init_app(user.views.blueprint, origins=origins)
    #cors.init_app(profile.views.blueprint, origins=origins)
    #cors.init_app(articles.views.blueprint, origins=origins)

    from app.api import api_blueprint
    app.register_blueprint(api_blueprint)
    #app.register_blueprint(user.views.blueprint)
    #app.register_blueprint(profile.views.blueprint)
    #app.register_blueprint(articles.views.blueprint)

    for moduleName in ('authentication','admin','files'):
        module = import_module('app.{}.routes'.format(moduleName))
        app.register_blueprint(module.blueprint)
    
from flask_login import current_user
from flask import flash, redirect, url_for, abort
from app.core.lib.object import getProperty

def check_page_access(request):
    _logger.debug(request)

    username = getattr(current_user, 'username', None)
    role = getattr(current_user, 'role', None)

    # TODO убрать открыто для admin ???
    if role == 'admin':
        return True
    
    # Извлекаем имя blueprint из endpoint
    parts = request.endpoint.split('.')
    if len(parts) > 1:
        blueprint_name = parts[0]  # Имя blueprint
    else:
        blueprint_name = "Core"  # Маршрут не принадлежит ни к одному blueprint

    endpoint = request.endpoint.replace(".", ":")
    permissions = None

    blueprint_permissions = getProperty("_permissions.blueprint:" + blueprint_name)
    if blueprint_permissions and isinstance(blueprint_permissions, dict):
        permissions = blueprint_permissions

    endpoint_permissions = getProperty("_permissions." + endpoint)
    if endpoint_permissions and isinstance(endpoint_permissions, dict):
        permissions = endpoint_permissions

    if permissions:
        permissions = permissions.get(request.method.lower(), None)

    if permissions:
        denied_users = permissions.get("denied_users",None) 
        if denied_users and username in denied_users:
            return False
        access_users = permissions.get("access_users",None) 
        if access_users and username in access_users:
            return True
        denied_roles = permissions.get("denied_roles",None) 
        if denied_roles and role in denied_roles:
            return False
        access_roles = permissions.get("access_roles",None) 
        if access_roles and role in access_roles:
            return True

    # Получаем функцию-обработчик для текущего маршрута
    view_func = current_app.view_functions.get(request.endpoint)

    # Проверяем, есть ли у функции атрибут required_role
    required_roles = getattr(view_func, 'required_roles', None)

    # для не заданных ролей считаем что открыто (FIXME потенциальная дыра в безопасности)
    if required_roles is None:
        return True

    # Пропускаем системные маршруты (например, /login, /static)
    if request.endpoint in ['static', 'login', 'logout']:
        return True

    # Проверяем, авторизован ли пользователь
    if not current_user.is_authenticated:
        _logger.warning(f"Unauthorized access attempt from {request.remote_addr} to {request.url}")
        return None

    # Проверяем роль пользователя
    if role in required_roles:
        return True

    return False

def registerErrorhandlers(app):

    @app.before_request
    def check_access():

        if request.endpoint is None:
            return
        
        if request.blueprint in ['auth']:
            return

        # Пропускаем аутентификацию для определенных маршрутов
        if request.endpoint in ['static']:
            return

        # Проверяем доступ к странице
        access = check_page_access(request)
        if access is None:
            flash('You need to log in first.', 'error')
            return redirect(url_for('auth.login'))
        if not access:
            abort(403)  # Возвращаем ошибку "Forbidden" если доступ запрещен

    def errorhandler(error):
        _logger.warning(error)
        response = error.to_json()
        response.status_code = error.status_code
        return response

    app.errorhandler(InvalidUsage)(errorhandler)

    # Обработчик ошибки 404
    @app.errorhandler(404)
    def page_not_found(error):
        _logger_error_http.info(f"404 error from {request.remote_addr}: {request.url}")
        return render_template('errors/page-404.html'), 404
    
    @app.errorhandler(403)
    def forbidden_error(error):
        _logger_error_http.warning(error)
        return render_template('errors/page-403.html'), 403
    
    @app.route('/forbidden')
    def access_forbidden():
        return render_template('errors/page-403.html'), 403


def registerShellcontext(app):
    """Register shell context objects."""
    def shell_context():
        """Shell context objects."""
        return {
            'db': db,
        }

    app.shell_context_processor(shell_context)


def registerCommands(app):
    """Register Click commands."""
    app.cli.add_command(commands.clean)
    app.cli.add_command(commands.urls)
    app.cli.add_command(commands.create_user)
