import sys, os, subprocess
from app.core.main.PluginsHelper import stop_plugins

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

    
    