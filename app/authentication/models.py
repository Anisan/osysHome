# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from app.extensions import login_manager
from app.core.models.Users import User
from app.core.lib.object import getObject

@login_manager.user_loader
def user_loader(id):
    obj = getObject(id)
    if not obj:
        return None
    user = User(obj)
    return user


@login_manager.request_loader
def request_loader(request):
    username = request.form.get('username')
    obj = getObject(username)
    if not obj:
        return None
    user = User(obj)
    return user
