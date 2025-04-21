# -*- coding: utf-8 -*-
"""Helper utilities and decorators."""
import datetime
from app.core.models.Users import User  # noqa
from app.core.lib.constants import PropertyType

def load_user(id):
    from app.core.lib.object import getObject
    obj = getObject(id)
    if not obj:
        return None
    user = User(obj)
    return user

def get_user_by_api_key(apikey):
    from app.core.lib.object import getObjectsByClass
    users = getObjectsByClass('Users')
    for user in users:
        if user.getProperty('apikey') and user.getProperty('apikey') == apikey:
            return User(user)
    return None

def initSystemVar():

    from app.core.lib.object import addClass,addClassProperty, addObject, getObject, setProperty, addObjectProperty, addObjectMethod, getObjectsByClass
    # Create permissions
    addObject("_permissions",None,"Permission settings")
    getObject("_permissions")  # preload

    # Create class users
    addClass('Users')
    addClassProperty('password', 'Users', 'Hash password')
    addClassProperty('role', 'Users', 'Role user')
    addClassProperty('home_page', 'Users', 'Home page for user (default: admin)')
    # Create SystemVar
    addObject("SystemVar",None,"System variable")
    addObjectMethod('isStarted',"SystemVar","Method for start",'say("System started");')
    addObjectProperty('Started','SystemVar',"Datetime starting system",0,PropertyType.Datetime,"isStarted")
    addObjectProperty('NeedRestart','SystemVar',"Need restart system",0,PropertyType.Bool)
    addObjectProperty('LastSay','SystemVar',"Last 'say' message",7,PropertyType.String)
    setProperty("SystemVar.Started",datetime.datetime.now(), "osysHome")
    setProperty("SystemVar.NeedRestart", False, "osysHome")

    users = getObjectsByClass('Users')
    if users is not None and len(users) != 0:
        initPermissions()

def initPermissions():
    from app.core.lib.object import setProperty, getProperty
    # set default permissions
    permissions_user = {"properties": {"role": {"get": {"access_roles": ["admin", "editor", "user"]},
                                                "set": {"access_roles": ["admin"], "denied_roles": ["editor", "user"]},
                                                "edit": {"access_roles": ["admin"], "denied_roles": ["editor", "user"]}}}}
    if getProperty("_permissions.class:Users") is None:
        setProperty("_permissions.class:Users", permissions_user)
