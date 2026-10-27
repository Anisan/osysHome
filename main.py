
"""Main module for start system"""
from app.configuration import Config
from app import createApp
from app.utils import initSystemVar, startSystemVar, init_analytics_scheduler, get_current_version
from app.core.main.PluginsHelper import start_plugins
from app.core.main.ObjectsStorage import objects_storage
from app.logging_config import getLogger
from app.graceful_shutdown import register_shutdown_handlers, graceful_shutdown

_logger = getLogger('main')

app = createApp(Config)

if __name__ == '__main__':
    _logger.info("osyHome version: %s", get_current_version())
    if getattr(Config, 'SECURITY_DEFAULTS_APPLIED', False):
        _logger.warning(
            "Security defaults were auto-applied (sample secret_key). "
            "Review config.yaml and store secret_key safely."
        )

    # SIGTERM (systemctl stop/restart), SIGINT, atexit — сброс BatchWriter/логов
    register_shutdown_handlers(app)

    _logger.info("Init SystemVar")
    with app.app_context():
        initSystemVar()

    _logger.info("Start plugins")
    start_plugins()

    with app.app_context():
        objects_storage.start_background_preload(app)

    startSystemVar()

    _logger.info("Init analytics scheduler")
    with app.app_context():
        init_analytics_scheduler()

    _logger.info("Run flask")
    app.run(
        host="0.0.0.0",
        debug=Config.DEBUG,
        use_reloader=False,
        port=Config.APP_PORT,
        threaded=True,
    )

    # Нормальный выход из app.run (не SIGTERM — тот уже обработан)
    graceful_shutdown('app.run returned')
