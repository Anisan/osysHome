# -*- coding: utf-8 -*-
"""Helper utilities and decorators."""
from .core.models.Users import User  # noqa
from .core.lib.object import getObject, getObjectsByClass

def load_user(id):
    obj = getObject(id)
    if not obj:
        return None
    user = User(obj)
    return user

def get_user_by_api_key(apikey):
    users = getObjectsByClass('Users')
    for user in users:
        if user.getProperty('apikey') and user.getProperty('apikey') == apikey:
            return User(user)
    return None