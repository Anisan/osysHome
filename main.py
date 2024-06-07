
"""Main module for start system"""

from settings import Config
from app import createApp
from app.core.main.ObjectsStorage import init_objects
from app.core.main.PluginsHelper import start_plugins, stop_plugins

app = createApp(Config)

if __name__ == '__main__':
    with app.app_context():
        init_objects()

    start_plugins()

    app.run(
        host="0.0.0.0",
        debug=Config.DEBUG,
        use_reloader=False,
        port=Config.APP_PORT,
        threaded=True,
    )

    stop_plugins()
