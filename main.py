
"""Main module for start system"""
import os
from flask_migrate import Migrate, upgrade, migrate, init, stamp
from settings import Config
from app import createApp
from app.utils import initSystemVar
from app.core.main.ObjectsStorage import init_objects
from app.core.main.PluginsHelper import start_plugins, stop_plugins

app = createApp(Config)

def perform_migrations():
    """Perform database migrations at runtime."""
    with app.app_context():
        try:
            if not os.path.exists(os.path.join(Config.APP_DIR, 'migrations')):
                init()
                stamp()
            migrate(message="Runtime migration.")
            upgrade()
        except Exception as e:
            print(f"Error during migration: {e}")

if __name__ == '__main__':

    #try:
        #perform_migrations()
    #except Exception as e:
        #print(f"Failed to perform migrations: {e}")

    with app.app_context():
        init_objects()

    start_plugins()

    with app.app_context():
        initSystemVar()

    app.run(
        host="0.0.0.0",
        debug=Config.DEBUG,
        use_reloader=False,
        port=Config.APP_PORT,
        threaded=True,
    )

    stop_plugins()
