# -*- coding: utf-8 -*-
"""Application configuration."""
import os
import logging

class Config(object):
    """Configuration."""
    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))  # This directory
    APP_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, 'app', os.pardir))
    ASSETS_ROOT = '/static/assets'
    PLUGINS_FOLDER = os.path.abspath(os.path.join(APP_DIR, "plugins"))
    DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs')
    FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files')

    DEFAULT_TIMEZONE = "Europe/Moscow"
    
    DEFAULT_LANGUAGE = 'en'
    # Settings app
    SECRET_KEY = 'secret-key'  # TODO: Change me
    """ Secret key for sessions """
    DEBUG = False
    """ Debug project (enable advanced information on logging)"""
    APP_PORT = 5000
    """ Http port server"""
    LOGGER_LEVEL = logging.INFO
    ENV = 'dev'

    POOL_SIZE = 20
    """ Number of worker threads for the application """

    # DB settings
    SQLALCHEMY_ECHO = False  # SQL log
    DB_NAME = 'app.db'
    # Put the db file in project root
    DB_PATH = os.path.join(APP_DIR, DB_NAME)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///{0}'.format(DB_PATH)
    # SQLALCHEMY_DATABASE_URI = 'postgresql://user:password@127.0.0.1/app'
    # SQLALCHEMY_DATABASE_URI = 'mysql://user:password@127.0.0.1/app'

    CACHE_FILE_PATH = "cache"  # Замените на путь к вашей папке кеша файлов

    CACHE_TYPE = 'simple'  # Can be "memcached", "redis", etc.
    CACHE_DEFAULT_TIMEOUT = 300  # Default timeout (sec). A timeout of 0 indicates that the cache never expires.
    # For redis
    # CACHE_REDIS_HOST = '127.0.0.1'
    # CACHE_REDIS_PORT = 6379
    # CACHE_REDIS_DB = 0
    # CACHE_REDIS_PASSWORD = None
    # CACHE_KEY_PREFIX = 'osys_'  # Префикс для всех ключей
    # CACHE_REDIS_SOCKET_TIMEOUT = 5      # Таймаут сокета
    # CACHE_REDIS_SOCKET_CONNECT_TIMEOUT = 5  # Таймаут подключения
    # CACHE_REDIS_MAX_CONNECTIONS = 20    # Максимальное количество соединений

    # Service auto restart
    SERVICE_AUTORESTART = False  # True if service option Restart=always
    # Service name
    SERVICE_NAME = None  # None or 'service_name'
