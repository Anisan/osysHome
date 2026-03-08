# -*- coding: utf-8 -*-
"""Helper utilities and decorators."""
import uuid
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
    addObjectProperty('welcome','SystemVar',"Show welcome message on control panel (first run)",0,PropertyType.Bool)
    if getProperty("SystemVar.welcome") is None:
        setProperty("SystemVar.welcome", True, "osysHome")

    type_editor = getProperty('SystemVar.code_editor')
    params = {
        "icon": 'fas fa-code',
        "enum_values":{
            'ace':'Ace editor',
            'monaco':'Monaco editor',
        }
    }
    addObjectProperty('code_editor','SystemVar',"Code editor",0, PropertyType.Enum, params=params, update=True)
    if type_editor == None:
        type_editor = 'monaco'
    setProperty('SystemVar.code_editor', type_editor)

    params = {
        "icon":"fas fa-grip",
        "enum_values":{
            'custom':'Customizable grid',
            'old':'Old style grid',
        },
        "default_value": 'custom',
    }
    addObjectProperty('control_panel_style','SystemVar',"Style control panel",0, PropertyType.Enum, params=params, update=True)

    # Analytics (opt-in, like Home Assistant). Enum: disabled=no, basic=version/plugins/counts, extended=future
    params = {
        "icon": "fas fa-chart-bar",
        "enum_values": {
            "disabled": "Disabled",
            "basic": "Basic",
            "extended": "Extended",
        },
    }
    addObjectProperty('analytics_enabled','SystemVar',"Analytics opt-in level",0, PropertyType.Enum, params=params, update=True)
    addObjectProperty('analytics_uuid','SystemVar',"Unique installation ID for analytics",0, PropertyType.String, update=True)
    if not getProperty("SystemVar.analytics_uuid"):
        setProperty("SystemVar.analytics_uuid", str(uuid.uuid4()).replace("-", ""), "osysHome")
    addObjectProperty('analytics_uuid','SystemVar',"Unique installation ID for analytics",0, PropertyType.String, params={"read_only": True}, update=True)

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


def init_analytics_scheduler():
    """Планирует отправку аналитики: первая через 15 мин (1 мин в DEBUG), далее раз в 24 ч."""
    from app.configuration import Config
    from app.core.lib.common import setTimeout, addCronJob, clearScheduledJob

    clearScheduledJob("osyshome_analytics%")
    code = "from app.analytics.sender import send_analytics; send_analytics()"
    first_delay = 60 if Config.DEBUG else 900  # 1 min в DEBUG, 15 мин в production
    setTimeout("osyshome_analytics_first", code, first_delay)
    # Ежедневная отправка в 4:00 (cron: мин час день мес день_недели)
    addCronJob("osyshome_analytics_daily", code, "0 4 * * *")

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
