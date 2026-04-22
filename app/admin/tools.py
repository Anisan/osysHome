import os
import subprocess
import ctypes
from app.configuration import Config 
from app.extensions import bcrypt
from app.core.lib.object import getObjectsByClass, getObject, addObject, setProperty

some_queue = None

def is_admin():
    """Проверяет, запущен ли скрипт с правами администратора."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def _is_running_in_docker():
    """Определяет, запущен ли процесс внутри Docker/контейнера."""
    if os.path.exists("/.dockerenv"):
        return True

    cgroup_path = "/proc/1/cgroup"
    if os.path.exists(cgroup_path):
        try:
            with open(cgroup_path, "r", encoding="utf-8") as f:
                cgroup_data = f.read()
            markers = ("docker", "containerd", "kubepods", "cri-o")
            return any(marker in cgroup_data for marker in markers)
        except OSError:
            return False
    return False


def _is_running_under_systemd():
    """Грубая эвристика запуска как systemd service."""
    if os.name == "nt":
        return False

    # Часто присутствуют, когда процесс запущен через systemd unit.
    if os.getenv("INVOCATION_ID") or os.getenv("JOURNAL_STREAM"):
        return True

    return False


def can_restart_system():
    """Возвращает True, если доступен хотя бы один способ перезапуска."""
    service_restart = getattr(Config, "SERVICE_AUTORESTART", False)
    docker_container = getattr(Config, "SERVICE_DOCKER_CONTAINER", None)
    service_name = getattr(Config, "SERVICE_NAME", None)

    return any([
        service_restart,
        bool(docker_container),
        bool(service_name),
        _is_running_in_docker(),
        _is_running_under_systemd(),
    ])


def restart_system():
    service_restart = Config.SERVICE_AUTORESTART
    if service_restart:
        # Завершаем процесс для внешнего менеджера (systemd/docker restart policy)
        print("Exiting with error to trigger external restart policy...")
        os._exit(1)

    docker_container = getattr(Config, "SERVICE_DOCKER_CONTAINER", None)
    if docker_container:
        try:
            subprocess.run(["docker", "restart", docker_container], check=True)
            return f"Docker container {docker_container} restarted successfully."
        except FileNotFoundError:
            return "Docker CLI is not available in PATH."
        except subprocess.CalledProcessError as e:
            return f"Failed to restart Docker container {docker_container}: {e}"

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
            return str(e)

    if _is_running_in_docker() or _is_running_under_systemd():
        # fallback, если явный способ не настроен
        print("Exiting with error to trigger external restart policy...")
        os._exit(1)

    return (
        "Restart target is not configured and launch mode is unknown. "
        "Set service.autorestart, service.docker_container, or service.name."
    )

def create_user(username, password):
    users = getObjectsByClass('Users')

    if not users:
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
