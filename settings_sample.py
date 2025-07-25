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

    # DB settings
    SQLALCHEMY_ECHO = False  # SQL log
    DB_NAME = 'app.db'
    # Put the db file in project root
    DB_PATH = os.path.join(APP_DIR, DB_NAME)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///{0}'.format(DB_PATH)
    # SQLALCHEMY_DATABASE_URI = 'postgresql://user:password@127.0.0.1/app'
    # SQLALCHEMY_DATABASE_URI = 'mysql://user:password@127.0.0.1/app'

    CACHE_FILE_PATH = "cache"  # Замените на путь к вашей папке кеша

    CACHE_TYPE = 'simple'  # Can be "memcached", "redis", etc.

    # Service auto restart
    SERVICE_AUTORESTART = False  # True if service option Restart=always
    # Service name
    SERVICE_NAME = None  # None or 'service_name'
