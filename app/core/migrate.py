import os
import subprocess
from settings import Config


def perform_migrations(message="Runtime migration."):
    """Perform database migrations at runtime."""
    try:
        # Проверка наличия папки migrations
        if not os.path.exists(os.path.join(Config.APP_DIR, "migrations")):
            # Инициализация миграций
            subprocess.run(["flask", "--app", "main.py", "db", "init"], check=True)
            subprocess.run(["flask", "--app", "main.py", "db", "stamp", "head"], check=True)

        # Создание новых миграций
        subprocess.run(["flask", "--app", "main.py", "db", "migrate", "-m", message], check=True)

        # Применение миграций
        subprocess.run(["flask", "--app", "main.py", "db", "upgrade"], check=True)

    except subprocess.CalledProcessError as e:
        print(f"Error during migration: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
