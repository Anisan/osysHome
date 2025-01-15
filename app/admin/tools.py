import sys, os, subprocess
import ctypes
from settings import Config 
from app.extensions import bcrypt
from app.core.main.PluginsHelper import stop_plugins
from app.core.lib.object import getObjectsByClass, getObject, addObject, setProperty

some_queue = None

def is_admin():
    """Проверяет, запущен ли скрипт с правами администратора."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False
    
def restart_system():
    service_restart = Config.SERVICE_RESTART
    if service_restart:
        # Завершаем скрипт
        print("Exiting with error to trigger systemd restart...")
        os._exit(1)
        return
    service_name = Config.SERVICE_NAME
    if service_name:
        try:
            if os.name == 'nt':  # Для Windows
                if not is_admin():
                    raise PermissionError("Script must be run as administrator to restart a service.")
                subprocess.run(["sc", "stop", service_name], check=True)
                subprocess.run(["sc", "start", service_name], check=True)
            else:  # Для Unix
                if os.geteuid() != 0:
                    raise PermissionError("Script must be run as root to restart a systemd service.")
                subprocess.run(["/usr/bin/systemctl", "restart", service_name], check=True)
            return f"Service {service_name} restarted successfully."
        except subprocess.CalledProcessError as e:
            return f"Failed to restart service {service_name}: {e}"
        except PermissionError as e:
            return e

def create_user(username, password):
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
