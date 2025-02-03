# -*- coding: utf-8 -*-
"""Helper utilities and decorators."""
import datetime
from .core.models.Users import User  # noqa
from .core.lib.object import getObject, getObjectsByClass, addObject, setProperty, addObjectProperty, addObjectMethod
from .core.lib.constants import PropertyType

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

def initSystemVar():
    addObject("SystemVar",None,"System variable")
    addObjectMethod('isStarted',"SystemVar","Method for start",'say("System started");')
    addObjectProperty('Started','SystemVar',"Datetime starting system",0,PropertyType.Datetime,"isStarted")
    addObjectProperty('NeedRestart','SystemVar',"Need restart system",0,PropertyType.Bool)
    setProperty("SystemVar.Started",datetime.datetime.now(), "osysHome")
    setProperty("SystemVar.NeedRestart", False, "osysHome")
