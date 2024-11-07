import sys, os, subprocess
from app.extensions import bcrypt
from app.core.main.PluginsHelper import stop_plugins
from app.core.main.ObjectsStorage import init_objects
from app.core.lib.object import getObjectsByClass, getObject, addObject, setProperty

some_queue = None

def restart_system():
    
    stop_plugins()
    os.execv(sys.executable, [sys.executable] + sys.argv)
    
    ##shutdown_server()
    # try:
    #     subprocess.run(['sudo', 'systemctl', 'restart', 'smh'], check=True)
    #     return "osysHome is restarting...", 200
    # except subprocess.CalledProcessError as e:
    #     return f"Error: {e}", 500

def create_user(username, password):
    init_objects()
    users = getObjectsByClass('Users')

    if users is None:
        return None

    obj = getObject(username)
    if obj:
        setProperty(username + ".password", bcrypt.generate_password_hash(password).decode('utf-8'))
        return 1
    else:
        obj = addObject(username,"Users")
        setProperty(username + ".password", bcrypt.generate_password_hash(password).decode('utf-8'))
        setProperty(username + ".role", 'user')
        return 2
