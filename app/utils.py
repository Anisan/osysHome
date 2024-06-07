# -*- coding: utf-8 -*-
"""Helper utilities and decorators."""
from .core.models.Users import User  # noqa
from .core.lib.object import getObject

def jwt_identity(payload):
    return User.get_by_id(payload)

def identity_loader(user):
    return user.username

def load_user(id):
    obj = getObject(id)
    if not obj:
        return None
    user = User(obj)
    return user