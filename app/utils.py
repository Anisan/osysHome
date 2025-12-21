# -*- coding: utf-8 -*-
"""Helper utilities and decorators."""
from pathlib import Path
import subprocess
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

    from app.core.lib.object import addClass, updateClass, addClassProperty, addObject, getObject, addObjectProperty, addObjectMethod, getObjectsByClass, getProperty, setProperty
    # Create permissions
    addObject("_permissions",None,"Permission settings")
    getObject("_permissions")  # preload

    # Create class users
    cls_user = addClass('Users','Users osysHome')
    if not cls_user['template']:
        # def template for Users
        cls_user['template'] = '''<div class="row">
    {% if object.image %}
    <img class="col pe-0" src="{{object.image}}"  style="width:auto;height:80px;object-fit:contain;" alt="{{object.name}}">
    {% endif %}
    <div class="col-auto">
        <h5 class="m-1">{{object.description}}</h5>
        Role: <b>{{object.role}}</b><br>
        Login: {{object.lastLogin}}
    </div>
</div>
'''
        updateClass(cls_user)
        
    addClassProperty('password', 'Users', 'Hash password', 0, type=PropertyType.String)
    addClassProperty('role', 'Users', 'Role user', 0, type=PropertyType.String)
    addClassProperty('home_page', 'Users', 'Home page for user (default: admin)', 0, type=PropertyType.String)
    addClassProperty('image', 'Users', 'User`s avatar', 0, type=PropertyType.String)
    addClassProperty('lastLogin', 'Users', 'Last login', 7, type=PropertyType.Datetime)
    addClassProperty('timezone', 'Users', 'Timezone user', 0, type=PropertyType.String)

    # Create SystemVar
    addObject("SystemVar",None,"System variable")
    addObjectMethod('isStarted',"SystemVar","Method for start",'say("System started");')
    addObjectProperty('Started','SystemVar',"Datetime starting system",0,PropertyType.Datetime,"isStarted")
    addObjectProperty('NeedRestart','SystemVar',"Need restart system",0,PropertyType.Bool)
    addObjectProperty('LastSay','SystemVar',"Last 'say' message",7,PropertyType.String)
    addObjectProperty('UnreadNotify','SystemVar',"Flag indicating the presence of an unread notification",0,PropertyType.Bool)
    addObjectProperty('LastNotify','SystemVar',"Last 'notify' message",7,PropertyType.Dictionary)

    type_editor = getProperty('SystemVar.code_editor')
    params = {
        "enum_values":{
            'ace':'Ace editor',
            'monaco':'Monaco editor',
        }
    }
    addObjectProperty('code_editor','SystemVar',"Code editor",0, PropertyType.Enum, params=params, update=True)
    if type_editor == None:
        type_editor = 'monaco'
    setProperty('SystemVar.code_editor', type_editor)

    users = getObjectsByClass('Users')
    if users:
        initPermissions()

def initPermissions():
    from app.core.lib.object import setProperty, getProperty
    # set default permissions
    permissions_user = {"properties": {"role": {"get": {"access_roles": ["admin", "editor", "user"]},
                                                "set": {"access_roles": ["admin"], "denied_roles": ["editor", "user"]},
                                                "edit": {"access_roles": ["admin"], "denied_roles": ["editor", "user"]}}}}
    if getProperty("_permissions.class:Users") is None:
        setProperty("_permissions.class:Users", permissions_user)

def startSystemVar():
    from app.core.lib.object import setProperty
    setProperty("SystemVar.Started",datetime.datetime.now(), "osysHome")
    setProperty("SystemVar.NeedRestart", False, "osysHome")

def get_current_version():
    ver_file = Path("VERSION")
    if ver_file.is_file():
        return ver_file.read_text().strip()
    # fallback: git describe
    try:
        desc = subprocess.check_output(
            ["git", "describe", "--tags", "--dirty", "--always"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        return desc.replace("-", "+", 1).replace("-", ".")  # v1.2.3-4-gabc → v1.2.3+4.gabc
    except:
        return "unknown"
