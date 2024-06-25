""" Main module """
from importlib import import_module
from flask import Flask, request, render_template
import flask_monitoringdashboard as dashboard
from . import commands
from .exceptions import InvalidUsage
from .constants import LANGUAGES
from .extensions import db, migrate, login_manager, cors, bcrypt, babel, toolbar, cache
from .core.main.PluginsHelper import *

from .logging_config import getLogger
_logger = getLogger('flask')

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
    if config_object.DEBUG:
        app.config['DEBUG_TB_TEMPLATE_EDITOR_ENABLED'] = True
        app.config['DEBUG_TB_PROFILER_ENABLED'] = True
        app.config['DEBUG_TB_PROFILER_DUMP_FILENAME'] = "dump.prof"
        app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] =False
        app.config['SQLALCHEMY_RECORD_QUERIES'] = True
    
    #from werkzeug.middleware.profiler import ProfilerMiddleware
    #app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[5], profile_dir='.')
   
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

    for moduleName in ('authentication','admin'):
        module = import_module('app.{}.routes'.format(moduleName))
        app.register_blueprint(module.blueprint)
    

def registerErrorhandlers(app):

    def errorhandler(error):
        response = error.to_json()
        response.status_code = error.status_code
        return response

    app.errorhandler(InvalidUsage)(errorhandler)

    # Обработчик ошибки 404
    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('errors/page-404.html'), 404
    
    @app.errorhandler(403)
    def forbidden_error(error):
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
