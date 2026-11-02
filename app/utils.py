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

_ON_SAY_DEFAULT_CODE = (
    'setProperty("SystemVar.LastSay", params.get("message"), source)\n'
)
_ON_NOTIFY_DEFAULT_CODE = (
    'if params and params.get("operation") == "added":\n'
    '    setProperty("SystemVar.LastNotify", params.get("data"), source)\n'
)


def initSystemVar():

    from app.core.lib.object import addClass, updateClass, addClassProperty, addObject, getObject, addObjectProperty, addObjectMethod, getObjectsByClass, getProperty, setProperty
    # Create permissions
    addObject("_permissions",None,"Permission settings")
    getObject("_permissions")  # preload

    # Create class users (protected — нельзя удалить/сменить родителя)
    cls_user = addClass(
        'Users', 'Users osysHome',
        params={"protected": True, "icon": "fas fa-users", "color": "#0d6efd"},
    )
    if not cls_user.get('template'):
        cls_user['template'] = USERS_CLASS_TEMPLATE
        updateClass(cls_user)

    from app.core.lib.object import markClassProtected
    markClassProtected('Users')

    addClassProperty(
        'password', 'Users', 'Hash password', 0, type=PropertyType.String,
        params={"protected": True,'icon': 'fas fa-key'},
    )
    addClassProperty(
        'role', 'Users', 'Role user', 0, type=PropertyType.String,
        params={"protected": True, 'icon': 'fas fa-user-tag'},
    )
    addClassProperty(
        'home_page', 'Users', 'Home page for user (default: admin)', 0, type=PropertyType.String,
        params={'icon': 'fas fa-home'},
    )
    addClassProperty(
        'image', 'Users', 'User`s avatar', 0, type=PropertyType.String,
        params={'icon': 'fas fa-image'},
    )
    addClassProperty(
        'lastLogin', 'Users', 'Last login', 7, type=PropertyType.Datetime,
        params={'icon': 'fas fa-clock'},
    )
    addClassProperty(
        'timezone', 'Users',
        'IANA timezone (e.g. Europe/Moscow) or auto for browser',
        0, type=PropertyType.String,
        params={'icon': 'fas fa-globe'},
    )

    # Create SystemVar
    def _sv_params(icon, **extra):
        p = {"protected": True, "icon": icon}
        p.update(extra)
        return p

    addObject(
        "SystemVar", None, "System variable",
        params={"protected": True, "icon": "fas fa-cogs", "color": "#6f42c1"},
    )
    # Хуки: код только при создании (update не затирает код пользователя).
    # Старт системы — onSystemStart; Started без привязки метода.
    for _hook_name, _hook_desc, _hook_code, _hook_icon in (
        ("onSay", "System event: say", _ON_SAY_DEFAULT_CODE, "fas fa-comment"),
        ("onPlaySound", "System event: playSound", "", "fas fa-volume-up"),
        ("onNotify", "System event: notify (added/confirmed/deleted)", _ON_NOTIFY_DEFAULT_CODE, "fas fa-bell"),
        ("onSystemStart", "System event: system start", 'say("System started");', "fas fa-play"),
        ("onSystemStop", "System event: system stop", "", "fas fa-stop"),
    ):
        _hook_params = _sv_params(_hook_icon)
        addObjectMethod(_hook_name, "SystemVar", _hook_desc, code=_hook_code, params=_hook_params)
        addObjectMethod(_hook_name, "SystemVar", _hook_desc, params=_hook_params)

    addObjectProperty(
        'Started', 'SystemVar', "Datetime starting system", 0,
        PropertyType.Datetime, "", params=_sv_params("fas fa-clock"),
    )
    addObjectProperty(
        'NeedRestart', 'SystemVar', "Need restart system", 0,
        PropertyType.Bool, params=_sv_params("fas fa-sync-alt"),
    )
    addObjectProperty(
        'core_branch', 'SystemVar', "Core update branch", 0,
        PropertyType.String, params=_sv_params("fas fa-code-branch"),
    )
    addObjectProperty(
        'core_url', 'SystemVar', "Core update repository URL", 0,
        PropertyType.String, params=_sv_params("fas fa-link"),
    )
    addObjectProperty(
        'upgraded', 'SystemVar', "Last core upgrade datetime", 0,
        PropertyType.Datetime, params=_sv_params("fas fa-arrow-up"),
    )
    addObjectProperty(
        'update', 'SystemVar', "Core update available", 0,
        PropertyType.Bool, params=_sv_params("fas fa-download"),
    )
    if getProperty("SystemVar.core_branch") is None:
        setProperty("SystemVar.core_branch", "master", "osysHome")
    if getProperty("SystemVar.core_url") is None:
        setProperty("SystemVar.core_url", "https://github.com/Anisan/osysHome", "osysHome")
    addObjectProperty(
        'LastSay', 'SystemVar', "Last 'say' message", 7,
        PropertyType.String, params=_sv_params("fas fa-comment"),
    )
    addObjectProperty(
        'UnreadNotify', 'SystemVar',
        "Flag indicating the presence of an unread notification", 0,
        PropertyType.Bool, params=_sv_params("fas fa-envelope"),
    )
    addObjectProperty(
        'LastNotify', 'SystemVar', "Last 'notify' message", 7,
        PropertyType.Dictionary, params=_sv_params("fas fa-bell"),
    )
    addObjectProperty(
        'error_rate_mute', 'SystemVar',
        "Muted error-rate notify fingerprints (mute_id -> meta)", 0,
        PropertyType.Dictionary, params=_sv_params("fas fa-bell-slash"),
    )
    if getProperty("SystemVar.error_rate_mute") is None:
        setProperty("SystemVar.error_rate_mute", {}, "osysHome")
    addObjectProperty(
        'welcome', 'SystemVar',
        "Show welcome message on control panel (first run)", 0,
        PropertyType.Bool, params=_sv_params("fas fa-door-open"),
    )
    if getProperty("SystemVar.welcome") is None:
        setProperty("SystemVar.welcome", True, "osysHome")

    type_editor = getProperty('SystemVar.code_editor')
    params = _sv_params(
        "fas fa-code",
        enum_values={
            'ace': 'Ace editor',
            'monaco': 'Monaco editor',
        },
    )
    addObjectProperty('code_editor', 'SystemVar', "Code editor", 0, PropertyType.Enum, params=params)
    if type_editor is None:
        type_editor = 'monaco'
    setProperty('SystemVar.code_editor', type_editor)

    params = _sv_params(
        "fas fa-grip",
        enum_values={
            'custom': 'Customizable grid',
            'old': 'Old style grid',
        },
        default_value='custom',
    )
    addObjectProperty(
        'control_panel_style', 'SystemVar', "Style control panel", 0,
        PropertyType.Enum, params=params,
    )

    # Analytics (opt-in, like Home Assistant). Enum: disabled=no, basic=version/plugins/counts, extended=future
    params = _sv_params(
        "fas fa-chart-bar",
        enum_values={
            "disabled": "Disabled",
            "basic": "Basic",
            "extended": "Extended",
        },
    )
    addObjectProperty(
        'analytics_enabled', 'SystemVar', "Analytics opt-in level", 0,
        PropertyType.Enum, params=params,
    )
    addObjectProperty(
        'analytics_uuid', 'SystemVar', "Unique installation ID for analytics", 0,
        PropertyType.String, params=_sv_params("fas fa-fingerprint"),
    )
    if not getProperty("SystemVar.analytics_uuid"):
        setProperty("SystemVar.analytics_uuid", str(uuid.uuid4()).replace("-", ""), "osysHome")
        from app.core.main.ObjectManager import _batch_writer
        _batch_writer.flush_sync()
    addObjectProperty(
        'analytics_uuid', 'SystemVar', "Unique installation ID for analytics", 0,
        PropertyType.String,
        params=_sv_params("fas fa-fingerprint", read_only=True),
    )

    addObjectProperty(
        'system_stats', 'SystemVar',
        "Enable local SystemStats history collection", 0,
        PropertyType.Bool, params=_sv_params("fas fa-chart-line"),
    )

    if getProperty("SystemVar.system_stats") is None:
        setProperty("SystemVar.system_stats", False, "osysHome")

    initSystemStats()

    users = getObjectsByClass('Users')
    if users:
        initPermissions()
        # Единственный пользователь (типичный первый admin) — защитить от удаления
        if len(users) == 1:
            from app.core.lib.object import markObjectProtected
            markObjectProtected(users[0].name)


_SQL_ENDPOINT_PERMISSIONS = {
    "api:select_query": {"get": {"access_roles": ["admin"]}},
    "api:exec_query": {"get": {"access_roles": ["admin"]}},
    "api:insert_query": {"post": {"access_roles": ["admin"]}},
    "api:update_query": {"post": {"access_roles": ["admin"]}},
}


def _merge_endpoint_permissions(defaults):
    """Добавляет права на endpoint, не перезаписывая настройки администратора."""
    from app.core.lib.object import setProperty, getProperty

    for endpoint, rules in defaults.items():
        key = "_permissions." + endpoint
        existing = getProperty(key)
        if existing is None:
            setProperty(key, rules)
            continue
        merged = dict(existing)
        changed = False
        for method, method_rules in rules.items():
            current = merged.get(method)
            if current is None:
                merged[method] = method_rules
                changed = True
                continue
            updated = dict(current)
            for rule_name, rule_value in method_rules.items():
                if rule_name not in updated:
                    updated[rule_name] = rule_value
                    changed = True
            merged[method] = updated
        if changed:
            setProperty(key, merged)


def initPermissions():
    from app.core.lib.object import setProperty, getProperty
    _merge_endpoint_permissions(_SQL_ENDPOINT_PERMISSIONS)
    # set default permissions
    permissions_user = {
        "properties": {
            "role": {
                "get": {"access_roles": ["admin", "editor", "user"]},
                "set": {"access_roles": ["admin"], "denied_roles": ["editor", "user"]},
                "edit": {"access_roles": ["admin"], "denied_roles": ["editor", "user"]},
            },
            "password": {
                "get": {"denied_roles": ["admin", "editor", "user"]},
                "set": {"access_roles": ["admin"]},
            },
            "apikey": {
                "get": {"access_roles": ["admin"]},
                "set": {"access_roles": ["admin"]},
            },
        }
    }
    existing = getProperty("_permissions.class:Users")
    if existing is None:
        setProperty("_permissions.class:Users", permissions_user)
        return

    merged = dict(existing)
    props = dict(merged.get("properties") or {})
    for prop_name, rules in permissions_user["properties"].items():
        current = props.get(prop_name)
        if not current:
            props[prop_name] = rules
            continue
        updated = dict(current)
        for op_name, op_rules in rules.items():
            if not updated.get(op_name):
                updated[op_name] = op_rules
        props[prop_name] = updated
    merged["properties"] = props
    if props != (existing.get("properties") or {}):
        setProperty("_permissions.class:Users", merged)

    _merge_system_stats_permissions()


_SYSTEM_STATS_PERMISSIONS = {
    "properties": {
        "*": {
            "get": {"access_roles": ["admin"]},
            "set": {"denied_roles": ["admin", "editor", "user"]},
            "edit": {"denied_roles": ["admin", "editor", "user"]},
        }
    },
    "methods": {
        "*": {
            "call": {"denied_roles": ["admin", "editor", "user"]},
        }
    },
}


def _merge_system_stats_permissions():
    from app.core.lib.object import setProperty, getProperty

    key = "_permissions.object:SystemStats"
    existing = getProperty(key)
    if existing is None:
        setProperty(key, _SYSTEM_STATS_PERMISSIONS)
        return
    merged = dict(existing)
    for section in ("properties", "methods"):
        section_data = dict(merged.get(section) or {})
        for name, rules in (_SYSTEM_STATS_PERMISSIONS.get(section) or {}).items():
            if name not in section_data:
                section_data[name] = rules
        merged[section] = section_data
    if merged != existing:
        setProperty(key, merged)

def startSystemVar():
    from app.core.lib.object import setProperty
    from app.core.lib.common import _callSystemVarHook
    # Локальное «сейчас»: тип datetime в setValue сам сделает convert_local_to_utc
    setProperty("SystemVar.Started", datetime.datetime.now(), "osysHome")
    setProperty("SystemVar.NeedRestart", False, "osysHome")
    _callSystemVarHook("onSystemStart", {"reason": "boot"}, "osysHome", async_=False)


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

def initSystemStats():
    from app.core.lib.object import addObject, addObjectProperty
    from app.core.lib.constants import PropertyType

    addObject("SystemStats", None, "System runtime statistics (internal)")

    properties = [
        ("property_reads", "Total property reads (excluding SystemStats)", PropertyType.Integer, 30),
        ("property_writes", "Total property writes (excluding SystemStats)", PropertyType.Integer, 30),
        ("methods_executed", "Total method calls (excluding SystemStats)", PropertyType.Integer, 30),
        ("batch_queue_size", "Current batch queue size", PropertyType.Integer, 30),
        ("batch_total_errors", "Total external batch write errors", PropertyType.Integer, 30),
        ("batch_avg_flush_ms", "Batch flush duration in ms (last flush)", PropertyType.Float, 30),
        ("batch_values_updated", "External value updates", PropertyType.Integer, 30),
        ("batch_history_inserted", "External history inserts", PropertyType.Integer, 30),
        ("reactive_loops", "Reactive loop counter", PropertyType.Integer, 30),
    ]

    internal_params = {"internal": True}

    for name, desc, ptype, history in properties:
        addObjectProperty(name, "SystemStats", desc, history, ptype, params=internal_params)


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
