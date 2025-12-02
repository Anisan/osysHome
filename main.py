
"""Main module for start system"""
from app.configuration import Config
from app import createApp
from app.utils import initSystemVar, startSystemVar, get_current_version
from app.core.main.PluginsHelper import start_plugins, stop_plugins
from app.logging_config import getLogger

_logger = getLogger('main')

app = createApp(Config)

if __name__ == '__main__':
    _logger.info("osyHome version: %s", get_current_version())

    _logger.info("Init SystemVar")
    with app.app_context():
        initSystemVar()

    _logger.info("Start plugins")
    start_plugins()

    startSystemVar()

    _logger.info("Run flask")
    app.run(
        host="0.0.0.0",
        debug=Config.DEBUG,
        use_reloader=False,
        port=Config.APP_PORT,
        threaded=True,
    )

    _logger.info("Stop plugins")
    stop_plugins()
