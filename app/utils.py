# -*- coding: utf-8 -*-
"""Helper utilities and decorators."""
import uuid
from pathlib import Path
import subprocess
import datetime
from app.core.models.Users import User  # noqa
from app.core.lib.constants import PropertyType

# Виджет класса Users на панели управления (Jinja2). Совпадает с рекомендуемым шаблоном в БД.
USERS_CLASS_TEMPLATE = """
<div class="users-cp-widget d-flex flex-column gap-2">
  <div class="d-flex align-items-start gap-3">
    {% if object.image %}
    <img src="{{ object.image|e }}" alt="" class="rounded-circle flex-shrink-0 shadow-sm border border-light" width="76" height="76" style="object-fit:cover;" loading="lazy">
    {% else %}
    <div class="rounded-circle flex-shrink-0 d-flex align-items-center justify-content-center bg-body-secondary text-secondary-emphasis border" style="width:76px;height:76px;">
      <i class="fas fa-user" style="font-size:2rem;opacity:0.85;"></i>
    </div>
    {% endif %}
    <div class="min-w-0 flex-grow-1">
      <div class="fw-semibold lh-sm text-truncate" title="{{ (object.description or object.name)|e }}">{{ object.description or object.name }}</div>
      <div class="small text-muted font-monospace text-truncate">{{ object.name }}</div>
      {% if object.role %}
      <span class="badge rounded-pill bg-primary bg-opacity-10 text-primary border border-primary border-opacity-25 mt-2">{{ object.role }}</span>
      {% endif %}
    </div>
  </div>
  {% if object.lastLogin or object.timezone or object.home_page %}
  <div class="d-flex flex-column gap-2 pt-2 border-top border-secondary border-opacity-25">
    {% if object.lastLogin %}
    <div class="d-flex align-items-start gap-2 small">
      <span class="text-primary mt-1"><i class="fas fa-clock fa-fw"></i></span>
      <div class="min-w-0">
        <div class="text-uppercase text-muted" style="font-size:0.65rem;letter-spacing:0.06em;">Last login</div>
        <div class="text-body-secondary">{{ object.lastLogin }}</div>
      </div>
    </div>
    {% endif %}
    {% if object.timezone %}
    <div class="d-flex align-items-start gap-2 small">
      <span class="text-primary mt-1"><i class="fas fa-globe fa-fw"></i></span>
      <div class="min-w-0">
        <div class="text-uppercase text-muted" style="font-size:0.65rem;letter-spacing:0.06em;">Timezone</div>
        <div class="text-body-secondary text-break">{{ object.timezone }}</div>
      </div>
    </div>
    {% endif %}
    {% if object.home_page %}
    <div class="d-flex align-items-start gap-2 small">
      <span class="text-primary mt-1"><i class="fas fa-home fa-fw"></i></span>
      <div class="min-w-0">
        <div class="text-uppercase text-muted" style="font-size:0.65rem;letter-spacing:0.06em;">Home page</div>
        <div class="text-body-secondary text-break">
          {% if object.home_page.startswith('http://') or object.home_page.startswith('https://') %}
          <a href="{{ object.home_page|e }}" target="_blank" rel="noopener noreferrer" class="link-primary">{{ object.home_page|e }}</a>
          {% else %}
          {{ object.home_page|e }}
          {% endif %}
        </div>
      </div>
    </div>
    {% endif %}
  </div>
  {% endif %}
</div>
""".strip()


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
        cls_user['template'] = USERS_CLASS_TEMPLATE
        updateClass(cls_user)

    addClassProperty(
        'password', 'Users', 'Hash password', 0, type=PropertyType.String,
        params={'icon': 'fas fa-key'}, update=True,
    )
    addClassProperty(
        'role', 'Users', 'Role user', 0, type=PropertyType.String,
        params={'icon': 'fas fa-user-tag'}, update=True,
    )
    addClassProperty(
        'home_page', 'Users', 'Home page for user (default: admin)', 0, type=PropertyType.String,
        params={'icon': 'fas fa-home'}, update=True,
    )
    addClassProperty(
        'image', 'Users', 'User`s avatar', 0, type=PropertyType.String,
        params={'icon': 'fas fa-image'}, update=True,
    )
    addClassProperty(
        'lastLogin', 'Users', 'Last login', 7, type=PropertyType.Datetime,
        params={'icon': 'fas fa-clock'}, update=True,
    )
    addClassProperty(
        'timezone', 'Users', 'Timezone user', 0, type=PropertyType.String,
        params={'icon': 'fas fa-globe'}, update=True,
    )

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
        from app.core.main.ObjectManager import _batch_writer
        _batch_writer.flush_sync()
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
