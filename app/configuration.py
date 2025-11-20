# -*- coding: utf-8 -*-
"""Application configuration."""
import os
import yaml
from pathlib import Path
from datetime import timedelta


class ConfigLoader(object):
    def __init__(self):
        """Base configuration."""
        self.DEBUG = True
        self.SECRET_KEY = 'secret-key'
        current_dir = os.path.abspath(os.path.dirname(__file__))
        self.APP_DIR = os.path.dirname(current_dir)
        self.PROJECT_ROOT = os.path.abspath(os.path.join(self.APP_DIR, os.pardir))
        # Assets Management
        self.ASSETS_ROOT = '/static/assets'
        self.PLUGINS_FOLDER = os.path.abspath(os.path.join(self.APP_DIR, "plugins"))
        self.DOCS_DIR = os.path.abspath(os.path.join(self.APP_DIR, 'docs'))
        self.FILES_DIR = os.path.abspath(os.path.join(self.APP_DIR, 'files'))

        self.APP_PORT = 5000
        self.ENV = 'dev'

        self.DEFAULT_TIMEZONE = "Europe/Moscow"

        self.POOL_SIZE = 30  # Размер пула потоков
        self.POOL_MAX_SIZE = None # Максимальный размер пула потоков (по-умолчанию 5*POOL_SIZE)
        self.POOL_TIMEOUT_THRESHOLD = 60.0  # Порог таймаута задач в секундах
        self.BATCH_WRITER_FLUSH_INTERVAL = 0.5  # Интервал записи батча в секундах

        # DB settings
        self.SQLALCHEMY_ECHO = False  # SQL log
        DB_NAME = 'app.db'
        # Put the db file in project root
        DB_PATH = os.path.join(self.APP_DIR, DB_NAME)
        self.SQLALCHEMY_DATABASE_URI = 'sqlite:///{0}'.format(DB_PATH)
        self.SQLALCHEMY_POOL_SIZE = 20  # Пул потоков для выполнения запросов к БД

        self.CACHE_FILE_PATH = "cache"  # Замените на путь к вашей папке кеша
        self.CACHE_DEFAULT_TIMEOUT = 300

        self.CACHE_TYPE = 'simple'  # Can be "memcached", "redis", etc.
        self.JWT_ACCESS_TOKEN_EXPIRES = timedelta(10 ** 6)

        # Service name systemd
        self.SERVICE_NAME = None  # None or 'service_name'
        self.SERVICE_AUTORESTART = False

    def load_from_file(self, config_file):
        """Загружает конфигурацию из YAML файла."""
        config_path = Path(config_file)

        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file {config_file} not found. "
                f"Please copy config_sample.yaml to {config_file} and configure it."
            )

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML configuration: {e}")

        app_config = self._config_data.get('application', {})
        self.DEFAULT_LANGUAGE = app_config.get('default_language', 'en')
        self.DEFAULT_TIMEZONE = app_config.get('default_timezone', 'Europe/Moscow')
        self.SECRET_KEY = app_config.get('secret_key', 'secret-key')
        self.DEBUG = app_config.get('debug', False)
        self.APP_PORT = app_config.get('app_port', 5000)
        self.ENV = app_config.get('env', 'dev')
        self.POOL_SIZE = app_config.get('pool_size', 20)
        self.POOL_MAX_SIZE = app_config.get('pool_max_size', None)
        self.POOL_TIMEOUT_THRESHOLD = app_config.get('pool_timeout_threshold', 60.0)
        self.BATCH_WRITER_FLUSH_INTERVAL = app_config.get('batch_writer_flush_interval', 0.5)

        db_config = self._config_data.get('database', {})
        self.SQLALCHEMY_ECHO = db_config.get('sqlalchemy_echo', False)
        self.SQLALCHEMY_POOL_SIZE = db_config.get('pool_size', 20)
        if 'connection_string' in db_config:
            self.SQLALCHEMY_DATABASE_URI = db_config['connection_string']
        else:
            DB_NAME = db_config.get('db_name', 'app.db')
            DB_PATH = os.path.join(self.APP_DIR, DB_NAME)
            self.SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'

        cache_config = self._config_data.get('cache', {})
        self.CACHE_FILE_PATH = os.path.abspath(os.path.join(self.APP_DIR, cache_config.get('file_path', 'cache')))
        self.CACHE_TYPE = cache_config.get('type', 'simple')
        self.CACHE_DEFAULT_TIMEOUT = cache_config.get('timeout', 300)

        service_config = self._config_data.get('service', {})
        self.SERVICE_AUTORESTART = service_config.get('autorestart', False)
        self.SERVICE_NAME = service_config.get('name', None)

def load_config(config_file='config.yaml'):
    """Удобная функция для загрузки конфигурации."""
    loader = ConfigLoader()
    loader.load_from_file(config_file)
    return loader


Config = load_config('config.yaml')
