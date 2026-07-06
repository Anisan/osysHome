""" Common library """
import threading
import time
from contextlib import contextmanager
import datetime
import re
from typing import Any, Literal, Optional, Union
from zoneinfo import ZoneInfo
from sqlalchemy import update, delete
import xml.etree.ElementTree as ET
from app.core.lib.execute import execute_and_capture_output
from app.logging_config import getLogger
from app.database import session_scope, row2dict, convert_local_to_utc, convert_utc_to_local, get_now_to_utc
from .crontab import nextStartCronJob
from .constants import (
    CategoryNotify,
    PropertyType,
    SYSTEM_STATS_OBJECT,
    SYSTEM_STATS_SOURCE,
    SYSTEM_STATS_PLUGIN_METRIC_PREFIX,
)
from ..main.PluginsHelper import plugins
from ..models.Tasks import Task
from ..models.Plugins import Notify
from app.core.MonitoredThreadPool import MonitoredThreadPool

_logger = getLogger("common")

# Глобальный пул потоков
_poolSay = MonitoredThreadPool(thread_name_prefix="say")
_poolPlaysound = MonitoredThreadPool(thread_name_prefix="playsound")

# Словарь для хранения блокировок, по одной на каждое имя задачи
_task_locks = {}
_task_locks_lock = threading.RLock()

@contextmanager
def get_task_lock(name: str):
    with _task_locks_lock:
        if name not in _task_locks:
            _task_locks[name] = threading.Lock()
        lock = _task_locks[name]
    acquire_result = lock.acquire()
    try:
        yield
    finally:
        if acquire_result:
            lock.release()


def addScheduledJob(
    name: str, code: str, dt: datetime.datetime, expire: int = 1800
) -> int:
    """Add scheduled job
    Args:
        name (str): Name schedule
        code (str): Python code
        dt (datetime): Datetime start job
        expire (int, optional): Expire time in minutes. Defaults to 1800.

    Returns:
        int: ID job or None
    """
    with get_task_lock(name):
        try:
            with session_scope() as session:
                task = session.query(Task).filter(Task.name == name).one_or_none()
                if not task:
                    task = Task()
                    task.name = name
                    session.add(task)
                task.code = code
                utc_dt = convert_local_to_utc(dt)
                task.runtime = utc_dt
                task.expire = utc_dt + datetime.timedelta(seconds=expire)
                task.active = True
                session.commit()
                return task.id
        except Exception as ex:
            _logger.exception(name, ex)
            return None


def addCronJob(name: str, code: str, crontab: str = "* * * * *") -> int:
    """Add cron job

    Args:
        name (str): Name
        code (str): Python code
        crontab (str, optional): Cron syntax period. Defaults to '* * * * *'.

    Returns:
        int: ID job or None
    """
    with get_task_lock(name):
        try:
            with session_scope() as session:
                dt = nextStartCronJob(crontab)
                task = session.query(Task).filter(Task.name == name).one_or_none()
                if not task:
                    task = Task()
                    task.name = name
                    session.add(task)
                task.code = code
                utc_dt = convert_local_to_utc(dt)
                task.runtime = utc_dt
                task.expire = utc_dt + datetime.timedelta(1800)
                task.crontab = crontab
                task.active = True
                session.commit()
                return task.id
        except Exception as ex:
            _logger.exception(name, ex)
            return None


def getJob(name: str) -> dict:
    """Get job data by name

    Args:
        name (str): Name job

    Returns:
        dict: Job data
    """
    with session_scope() as session:
        job = session.query(Task).filter(Task.name == name).one_or_none()
        if job:
            return row2dict(job)
        return None

def getJobs(query: str) -> list:
    """Get jobs by name contain query

    Args:
        query (str): Query

    Returns:
        list: Jobs
    """
    with session_scope() as session:
        result = session.query(Task).filter(Task.name.like(query)).all()
        if result:
            jobs = []
            for task in result:
                jobs.append(row2dict(task))
            return jobs
        return []


def clearScheduledJob(name: str):
    """Clear jobs contains name

    Args:
        name (str): Name for search
    """
    with get_task_lock(name):
        with session_scope() as session:
            sql = delete(Task).where(Task.name.like(name))
            session.execute(sql)
            session.commit()

def setTimeout(name: str, code: str, timeout: int = 0):
    """Set timeout for run code

    Args:
        name (str): Name timeout
        code (str): Python code
        timeout (int, optional): Timeout in seconds. Defaults to 0.

    Returns:
        _type_: _description_
    """
    local_dt = convert_utc_to_local(get_now_to_utc())
    res = addScheduledJob(
        name, code, local_dt + datetime.timedelta(seconds=timeout)
    )
    return res


def clearTimeout(name: str):
    """Clear timeout by name

    Args:
        name (str): Name
    """
    clearScheduledJob(name)


def enableJob(name: str) -> bool:
    """Enable job by name

    Args:
        name (str): Name job

    Returns:
        bool: Success
    """
    with get_task_lock(name):
        try:
            with session_scope() as session:
                task = session.query(Task).filter(Task.name == name).one_or_none()
                if task:
                    task.active = True
                    session.commit()
                    return True
                return False
        except Exception as ex:
            _logger.exception(name, ex)
            return False


def disableJob(name: str) -> bool:
    """Disable job by name

    Args:
        name (str): Name job

    Returns:
        bool: Success
    """
    with get_task_lock(name):
        try:
            with session_scope() as session:
                task = session.query(Task).filter(Task.name == name).one_or_none()
                if task:
                    task.active = False
                    session.commit()
                    return True
                return False
        except Exception as ex:
            _logger.exception(name, ex)
            return False


def getModule(name: str):
    """Get instance module by name
    Args:
        name (str): Name module
    Returns:
        any: Module instance
    """
    if name not in plugins:
        return None
    return plugins[name]["instance"]

def getModulesByAction(action: str):
    """Get modules by action
    Args:
        action (str): Action
    Returns:
        list: List of modules
    """
    return [module["instance"] for _, module in plugins.items() if action in module["instance"].actions]


def callPluginFunction(plugin: str, func: str, args=None):
    """Call a public method on a loaded plugin instance.

    Args:
        plugin: Plugin name (folder name), e.g. ``YandexDevices``.
        func: Method name on the plugin class.
        args: Keyword arguments passed to the method (``dict``).

    Returns:
        Whatever the plugin method returns, or ``None`` if the plugin or method
        is missing or the call raised an exception.
    """
    if args is None:
        args = {}
    if plugin not in plugins:
        _logger.error("Plugin '%s' not found.", plugin)
        return None
    plugin_obj = plugins[plugin]["instance"]

    if hasattr(plugin_obj, func):
        function = getattr(plugin_obj, func)
        try:
            return function(**args)
        except Exception as ex:
            _logger.exception(ex)
            return None
    _logger.error("Function '%s' not found in plugin %s.", func, plugin)
    return None


def say(message: str, level: int = 0, args: dict = None):
    """Say

    Args:
        message (_type_): Message
        level (int, optional): Level. Defaults to 0.
        args (dict, optional): Arguments. Defaults to None.
    """
    from .object import setProperty
    source = args.get("source", "osysHome") if args else "osysHome"
    setProperty("SystemVar.LastSay", message, source)
    modules_with_say = getModulesByAction("say")
    for plugin in modules_with_say:
        try:
            _poolSay.submit(plugin.say, f"say_{plugin.name}", message, level, args)
        except Exception as ex:
            _logger.exception(ex)


def playSound(file_name: str, level: int = 0, args: dict = None):
    """Play sound

    Args:
        file_name (_type_): Path media file
        level (int, optional): Level. Defaults to 0.
        args (dict, optional): Arguments. Defaults to None.
    """
    modules_with_playsound = getModulesByAction("playsound")
    for plugin in modules_with_playsound:
        try:
            _poolPlaysound.submit(plugin.playSound, f"playsound_{plugin.name}", file_name, level, args)
        except Exception as ex:
            _logger.exception(ex)


def addNotify(
    name: str,
    description: str = "",
    category: CategoryNotify = CategoryNotify.Info,
    source="",
):
    """Add notify

    Args:
        name (str): Text notify
        description (str, optional): Description notify. Defaults to "".
        category (CategoryNotify, optional): Category. Defaults to CategoryNotify.Info.
        source (str, optional): Source notify (use name plugins). Defaults to "".
    """
    notify_id = None
    notify_count = 1
    with session_scope() as session:
        notify = session.query(Notify).filter(Notify.name == name, Notify.description == description, Notify.read == False).first() # noqa
        if notify:
            notify.count = (notify.count if notify.count else 0) + 1
            notify.last_updated = get_now_to_utc()
            notify_id = notify.id
            notify_count = notify.count
            session.commit()
        else:
            notify = Notify()
            notify.name = name
            notify.description = description
            notify.category = category
            notify.source = source
            notify.created = get_now_to_utc()
            notify.last_updated = get_now_to_utc()
            notify.count = 1
            session.add(notify)
            session.flush()
            notify_id = notify.id
            notify_count = 1

    from .object import setProperty
    data = {
        "name": name,
        "description": description,
        "category": category.value,
        "source": source,
    }
    setProperty("SystemVar.LastNotify", data, source)
    setProperty("SystemVar.UnreadNotify", True, source)

    # Отправляем событие через WebSocket
    notify_data = {
        "operation": "new_notify",
        "data": {
            "id": notify_id,
            "name": name,
            "description": description,
            "category": category.value,
            "source": source,
            "count": notify_count,
        }
    }
    callPluginFunction("wsServer","notify", {"data":notify_data})


def readNotify(notify_id: int):
    """Set read for notify

    Args:
        notify_id (int): ID notify
    """
    notify_source = None
    notify_found = False
    with session_scope() as session:
        # Получаем информацию об уведомлении перед обновлением
        notify = session.query(Notify).filter(Notify.id == notify_id).first()
        if notify:
            notify_source = notify.source
            notify_found = True

        if notify_found:
            sql = update(Notify).where(Notify.id == notify_id).values(read=True, read_date=get_now_to_utc())
            session.execute(sql)
            session.commit()

        findUnread = session.query(Notify).filter(Notify.read == False).first()  # noqa
        from .object import updateProperty
        if findUnread:
            updateProperty("SystemVar.UnreadNotify", True)
        else:
            updateProperty("SystemVar.UnreadNotify", False)

    # Отправляем событие через WebSocket (даже если уведомление не найдено, чтобы обновить интерфейс)
    notify_data = {\
        "operation": "read_notify",
        "data": {
            "id": notify_id,
            "source": notify_source or "",
        }
    }
    callPluginFunction("wsServer","notify", {"data":notify_data})

    return True

def readNotifyAll(source: Optional[str] = None):
    """Set read all notify for source

    Args:
        source (str, optional): Source notify. If None or empty, marks all notifications as read.
    """
    with session_scope() as session:
        if source:
            sql = update(Notify).where(Notify.source == source).values(read=True, read_date=get_now_to_utc())
        else:
            # Если source не указан, отмечаем все уведомления
            sql = update(Notify).values(read=True, read_date=get_now_to_utc())
        session.execute(sql)
        session.commit()

        findUnread = session.query(Notify).filter(Notify.read == False).first()  # noqa
        from .object import updateProperty
        if findUnread:
            updateProperty("SystemVar.UnreadNotify", True)
        else:
            updateProperty("SystemVar.UnreadNotify", False)

    # Отправляем событие через WebSocket
    notify_data = {
        "operation": "read_notify_all", 
        "data": 
        {
            "source": source or "all",
        }
    }
    callPluginFunction("wsServer","notify", {"data":notify_data})


def requestUrl(
    url: str,
    method: str = "GET",
    params: dict = None,
    headers: dict = None,
    json_data: dict = None,
    data: dict = None,
    cookies: dict = None,
    timeout: float = None,
) -> Optional[bytes]:
    """Выполнить HTTP-запрос и вернуть содержимое ответа.

    Args:
        url: URL для запроса
        method: HTTP-метод (GET, POST, PUT, PATCH, DELETE и др.)
        params: query-параметры URL (для GET и др.)
        headers: заголовки запроса
        json_data: JSON-тело запроса (для POST, PUT и др.)
        data: тело запроса (form-data, для POST и др.)
        cookies: словарь cookies {name: value}
        timeout: таймаут в секундах (по умолчанию Config.HTTP_REQUEST_TIMEOUT)

    Returns:
        bytes: содержимое ответа или None при ошибке
    """
    import requests
    from app.configuration import Config

    timeout = timeout if timeout is not None else Config.HTTP_REQUEST_TIMEOUT

    try:
        result = requests.request(
            method=method.upper(),
            url=url,
            params=params,
            headers=headers,
            json=json_data,
            data=data,
            cookies=cookies,
            timeout=timeout,
        )
        return result.content
    except Exception as e:
        _logger.exception(e)
    return None


def getUrl(
    url: str,
    params: dict = None,
    headers: dict = None,
    cookies: dict = None,
    timeout: float = None,
) -> Optional[bytes]:
    """GET-запрос (alias для requestUrl с method='GET')."""
    return requestUrl(
        url, method="GET", params=params, headers=headers, cookies=cookies, timeout=timeout
    )


def postUrl(
    url: str,
    params: dict = None,
    headers: dict = None,
    json_data: dict = None,
    data: dict = None,
    cookies: dict = None,
    timeout: float = None,
) -> Optional[bytes]:
    """POST-запрос (alias для requestUrl с method='POST')."""
    return requestUrl(
        url,
        method="POST",
        params=params,
        headers=headers,
        json_data=json_data,
        data=data,
        cookies=cookies,
        timeout=timeout,
    )


def putUrl(
    url: str,
    params: dict = None,
    headers: dict = None,
    json_data: dict = None,
    data: dict = None,
    cookies: dict = None,
    timeout: float = None,
) -> Optional[bytes]:
    """PUT-запрос (alias для requestUrl с method='PUT')."""
    return requestUrl(
        url,
        method="PUT",
        params=params,
        headers=headers,
        json_data=json_data,
        data=data,
        cookies=cookies,
        timeout=timeout,
    )


def patchUrl(
    url: str,
    params: dict = None,
    headers: dict = None,
    json_data: dict = None,
    data: dict = None,
    cookies: dict = None,
    timeout: float = None,
) -> Optional[bytes]:
    """PATCH-запрос (alias для requestUrl с method='PATCH')."""
    return requestUrl(
        url,
        method="PATCH",
        params=params,
        headers=headers,
        json_data=json_data,
        data=data,
        cookies=cookies,
        timeout=timeout,
    )


def deleteUrl(
    url: str,
    params: dict = None,
    headers: dict = None,
    cookies: dict = None,
    timeout: float = None,
) -> Optional[bytes]:
    """DELETE-запрос (alias для requestUrl с method='DELETE')."""
    return requestUrl(
        url, method="DELETE", params=params, headers=headers, cookies=cookies, timeout=timeout
    )


def sendWebsocket(command: str, data: any, client_id:str=None) -> bool:
    """Send command to websocket
    Args:
        command (str): Command
        data (any): Data
        client_id(str): Client ID (None - send all)
    Returns:
        bool: Success
    """
    if "wsServer" not in plugins:
        return False

    plugin_obj = plugins["wsServer"]["instance"]

    if hasattr(plugin_obj, "sendCommand"):
        function = getattr(plugin_obj, "sendCommand")
        try:
            return function(command, data, client_id)
        except Exception as ex:
            _logger.exception(ex)
            return False
    else:
        _logger.error("Function '%s' not found in plugin %s.", "sendCommand", "wsServer")
        return False

def sendDataToWebsocket(typeData: str, data: any) -> bool:
    """Send data to websocket
    Args:
        typeData (str): Type data
        data (any): Data
    Returns:
        bool: Success
    """
    if "wsServer" not in plugins:
        return False

    plugin_obj = plugins["wsServer"]["instance"]

    if hasattr(plugin_obj, "sendData"):
        function = getattr(plugin_obj, "sendData")
        try:
            return function(typeData, data)
        except Exception as ex:
            _logger.exception(ex)
            return False
    else:
        _logger.error("Function '%s' not found in plugin %s.", "sendData", "wsServer")
        return False


def xml_to_dict(xml_data) -> dict:
    """Convert xml to dictionary

    Args:
        xml_data (str): XML string

    Returns:
        dict: Dictionary
    """
    def recursive_dict(element):
        node = {}
        if element.attrib:
            node.update(("@" + k, v) for k, v in element.attrib.items())
        children = list(element)
        if children:
            child_dict = {}
            for child in children:
                child_key, child_value = recursive_dict(child)
                if child_key in child_dict:
                    if not isinstance(child_dict[child_key], list):
                        child_dict[child_key] = [child_dict[child_key]]
                    child_dict[child_key].append(child_value)
                else:
                    child_dict[child_key] = child_value
            node.update(child_dict)
        else:
            node = element.text

        return element.tag, node

    root = ET.fromstring(xml_data)

    return {root.tag: recursive_dict(root)[1]}


def runCode(code: str, args=None):
    """Run code

    Args:
        code (str): Python code
        args (dict, optional): Arguments. Defaults to None.

    Return:
        any, bool: Result
    """
    # append common
    try:
        variables = {
            "params": args,
            "logger": _logger,
        }
        output, error = execute_and_capture_output(code, variables)

        return output, not error
    except Exception as ex:
        _logger.exception(ex)
        return str(ex), False

def is_datetime_in_range(
    check_dt: Optional[datetime.datetime],
    start_dt: Optional[datetime.datetime],
    end_dt: Optional[datetime.datetime],
    inclusive: Union[bool, str] = True,
) -> bool:
    """
    Checks whether check_dt is between start_dt and end_dt.

    Parameters:
        check_dt: The datetime to check.
        start_dt: The start of the range (None = -∞).
        end_dt: The end of the range (None = +∞).
        inclusive: Boundary inclusion:
        - True (default): both boundaries are included [start_dt, end_dt].
        - False: both boundaries are excluded (start_dt, end_dt).
        - "left": only start_dt is included [start_dt, end_dt).
        - "right": only end_dt is included (start_dt, end_dt].

    Returns:
        bool: True if check_dt falls within the range.
    """
    # Нормализуем все даты к наивному UTC, чтобы избежать ошибок сравнения
    def _to_naive_utc(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt
        return dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    check_dt = _to_naive_utc(check_dt)
    # Если дата для проверки не указана, нельзя корректно определить попадание в диапазон
    if check_dt is None:
        return False
    start_dt = _to_naive_utc(start_dt)
    end_dt = _to_naive_utc(end_dt)

    if start_dt is not None:
        if inclusive in (True, "left"):
            if check_dt < start_dt:
                return False
        else:
            if check_dt <= start_dt:
                return False

    if end_dt is not None:
        if inclusive in (True, "right"):
            if check_dt > end_dt:
                return False
        else:
            if check_dt >= end_dt:
                return False

    return True


_MALE_GENDER_STRINGS = frozenset({
    'male', 'man', 'm', '1', 'true',
    'мужчина', 'мужской', 'мужское', 'мужского', 'муж', 'м',
})
_FEMALE_GENDER_STRINGS = frozenset({
    'female', 'woman', 'f', '0', 'false',
    'женщина', 'женский', 'женской', 'женское', 'женского', 'жен', 'ж',
})
_UNKNOWN_GENDER_STRINGS = frozenset({
    'unknown', 'unk', 'none', 'null',
    'неизвестно', 'не указан', 'не указано', 'any', 'neutral', 'нейтральный',
})

GenderKey = Literal['male', 'female', 'unknown']


def normalize_gender(gender: Any) -> GenderKey:
    """
    Приводит значение пола к одному из: 'male', 'female', 'unknown'.

    Строки нормализуются (strip + casefold). Число 1 и bool True — мужской пол.
    Число 0 — женский пол. bool False, None и пустая строка — неизвестный пол.
    """
    if gender is None:
        return 'unknown'
    if isinstance(gender, bool):
        return 'male' if gender else 'female'
    if isinstance(gender, int):
        if gender == 1:
            return 'male'
        if gender == 0:
            return 'female'
        return 'unknown'
    if isinstance(gender, str):
        key = gender.strip().casefold()
        if not key or key in _UNKNOWN_GENDER_STRINGS:
            return 'unknown'
        if key in _MALE_GENDER_STRINGS:
            return 'male'
        if key in _FEMALE_GENDER_STRINGS:
            return 'female'
        return 'unknown'
    return 'unknown'


def inflect_by_gender(
    gender: Any,
    base: str,
    male_end: str,
    female_end: str,
    default_end: str = '',
) -> str:
    """
    Склоняет слово (или фразу) по полу, добавляя к основе нужное окончание.

    Удобно для русских текстов в сценариях и уведомлениях: «он пришёл» / «она пришла»,
    «готов» / «готова» и т.п. — передаёте основу и суффиксы, функция возвращает
    base + male_end | base + female_end | base + default_end.

    Args:
        gender: Пол (см. normalize_gender). Неизвестное значение → default_end.
        base: Основа слова без окончания (например, «готов»).
        male_end: Окончание для мужского рода (например, «» или «ой»).
        female_end: Окончание для женского рода (например, «а»).
        default_end: Окончание при неопределённом поле; по умолчанию '' (нейтральная
            форма совпадает с base).

    Returns:
        str: Склеенная строка base + суффикс.

    Example:
        inflect_by_gender('female', 'готов', '', 'а')  # 'готова'
        inflect_by_gender(1, 'он ', 'пришёл', 'пришла')  # 'он пришёл'
        inflect_by_gender(None, 'готов', '', 'а')  # 'готов'
        inflect_by_gender(0, 'готов', '', 'а')  # 'готова'
    """
    match normalize_gender(gender):
        case 'male':
            return base + male_end
        case 'female':
            return base + female_end
        case _:
            return base + default_end


def _is_system_stats_metric_registered(property_key: str) -> bool:
    """Return True if metric property already exists (runtime cache, memory, or DB)."""
    with _registered_system_stats_metrics_lock:
        if property_key in _registered_system_stats_metrics:
            return True

    from app.core.main.ObjectsStorage import objects_storage

    obj = objects_storage.getObjectByName(SYSTEM_STATS_OBJECT)
    if obj and property_key in obj.properties:
        with _registered_system_stats_metrics_lock:
            _registered_system_stats_metrics.add(property_key)
        return True

    from app.core.models.Clasess import Object, Property

    with session_scope() as session:
        stats_obj = (
            session.query(Object)
            .filter(Object.name == SYSTEM_STATS_OBJECT)
            .one_or_none()
        )
        if stats_obj and (
            session.query(Property)
            .filter(Property.name == property_key, Property.object_id == stats_obj.id)
            .one_or_none()
        ):
            with _registered_system_stats_metrics_lock:
                _registered_system_stats_metrics.add(property_key)
            return True
    return False


def registerSystemStatsMetric(
    plugin_name: str,
    metric_name: str,
    *,
    description: str = "",
    history: int = 30,
    prop_type: PropertyType = PropertyType.Float,
) -> str:
    """Create metric property on `SystemStats` for event-driven writes.

    Returns property key only (without ``SystemStats.`` prefix).
    """
    property_key = _system_stats_metric_key(plugin_name, metric_name)
    if _is_system_stats_metric_registered(property_key):
        return property_key

    from .object import addObjectProperty

    addObjectProperty(
        property_key,
        SYSTEM_STATS_OBJECT,
        description or f"{plugin_name}: {metric_name}",
        history,
        prop_type,
        params={"internal": True, "plugin_metric": True},
        update=True,
    )
    with _registered_system_stats_metrics_lock:
        _registered_system_stats_metrics.add(property_key)
    return property_key


def writeSystemStatsMetric(
    plugin_name: str,
    metric_name: str,
    value: Any,
    *,
    description: str = "",
    history: int = 30,
    prop_type: PropertyType = PropertyType.Float,
    source: str = "",
) -> bool:
    """Write plugin metric to SystemStats with forced ``track_stats=False``.

    This function is event-driven and does not rely on cron collectors.
    """
    from .object import updateProperty
    if not _is_system_stats_enabled():
        return False
    property_key = registerSystemStatsMetric(
        plugin_name,
        metric_name,
        description=description,
        history=history,
        prop_type=prop_type,
    )
    full_name = f"{SYSTEM_STATS_OBJECT}.{property_key}"
    metric_source = source or f"{SYSTEM_STATS_SOURCE}:{plugin_name}"
    return updateProperty(full_name, value, source=metric_source, track_stats=False)


def incrementSystemStatsMetric(
    plugin_name: str,
    metric_name: str,
    step: Union[int, float] = 1,
    *,
    description: str = "",
    history: int = 30,
    source: str = "",
) -> bool:
    """Increment numeric metric with forced ``track_stats=False``."""
    if not _is_system_stats_enabled():
        return False
    property_key = _system_stats_metric_key(plugin_name, metric_name)
    current = _read_system_stats_property_value(property_key)
    if current is None:
        current = 0
    try:
        current_val = float(current)
    except Exception:
        current_val = 0.0
    new_val = current_val + step
    return writeSystemStatsMetric(
        plugin_name,
        metric_name,
        new_val,
        description=description,
        history=history,
        prop_type=PropertyType.Float if isinstance(new_val, float) else PropertyType.Integer,
        source=source,
    )


def unregisterSystemStatsMetric(plugin_name: str, metric_name: str) -> None:
    # No in-memory registry anymore; metric keys remain in SystemStats object.
    return None


def unregisterSystemStatsPlugin(plugin_name: str) -> None:
    """No-op in event-driven mode without registry."""
    return None


def _system_stats_metric_key(plugin_name: str, metric_name: str) -> str:
    safe_metric = re.sub(r"[^a-zA-Z0-9_]", "_", str(metric_name or "").strip())
    if not safe_metric:
        safe_metric = "metric"
    return f"{SYSTEM_STATS_PLUGIN_METRIC_PREFIX}{plugin_name}_{safe_metric}"


# Hot-path core metrics: accumulate in memory, flush with BatchWriter (~flush_interval).
_BUFFERED_CORE_METRICS = frozenset({
    "property_reads",
    "property_writes",
    "methods_executed",
    "reactive_loops",
})

_SYSTEM_STATS_ENABLED_CACHE_TTL = 2.0
_system_stats_enabled_cache: Optional[bool] = None
_system_stats_enabled_cache_at: float = 0.0
_system_stats_enabled_cache_lock = threading.Lock()

_SYSTEM_STATS_WS_DEBOUNCE_SEC = 0.5
_system_stats_ws_pending: dict[tuple[str, str], Any] = {}
_system_stats_ws_lock = threading.Lock()
_system_stats_ws_timer: Optional[threading.Timer] = None

_registered_system_stats_metrics: set[str] = set()
_registered_system_stats_metrics_lock = threading.Lock()

# Serializes buffered flush + DB increment (per process); row lock covers multi-worker.
_stats_apply_lock = threading.Lock()


class _CoreSystemStatsBuffer:
    """In-memory deltas for high-frequency core metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, Union[int, float]] = {}

    def increment(self, metric_name: str, step: Union[int, float] = 1) -> None:
        with self._lock:
            self._pending[metric_name] = self._pending.get(metric_name, 0) + step

    def flush(self) -> None:
        if not _is_system_stats_enabled():
            with self._lock:
                self._pending.clear()
            return
        with self._lock:
            pending = self._pending
            self._pending = {}
        for metric_name, delta in pending.items():
            if not delta:
                continue
            _apply_core_system_stats_delta(metric_name, delta)


_core_stats_buffer = _CoreSystemStatsBuffer()


def scheduleSystemStatsWsNotify(object_name: str, property_name: str, value: Any) -> None:
    """Debounce WebSocket updates for SystemStats subscriptions."""
    global _system_stats_ws_timer
    key = (object_name, property_name)
    with _system_stats_ws_lock:
        _system_stats_ws_pending[key] = value
        if _system_stats_ws_timer is not None:
            _system_stats_ws_timer.cancel()
        _system_stats_ws_timer = threading.Timer(
            _SYSTEM_STATS_WS_DEBOUNCE_SEC,
            flushSystemStatsWsNotifications,
        )
        _system_stats_ws_timer.daemon = True
        _system_stats_ws_timer.start()


def flushSystemStatsWsNotifications() -> None:
    global _system_stats_ws_timer
    with _system_stats_ws_lock:
        pending = dict(_system_stats_ws_pending)
        _system_stats_ws_pending.clear()
        _system_stats_ws_timer = None
    if not pending:
        return
    ws = getModule("wsServer")
    if not ws or not hasattr(ws, "changeProperty"):
        return
    for (obj_name, prop_name), val in pending.items():
        try:
            ws.changeProperty(obj_name, prop_name, val)
        except Exception as ex:
            _logger.exception(ex)


def flushBufferedCoreSystemStatsMetrics() -> None:
    """Flush buffered core metric deltas (called from BatchWriter tick)."""
    _core_stats_buffer.flush()


def invalidateSystemStatsEnabledCache() -> None:
    global _system_stats_enabled_cache
    with _system_stats_enabled_cache_lock:
        _system_stats_enabled_cache = None


def _get_system_stats_property_manager(metric_name: str):
    from app.core.main.ObjectsStorage import objects_storage
    obj = objects_storage.getObjectByName(SYSTEM_STATS_OBJECT)
    if not obj or metric_name not in obj.properties:
        return None, None
    return obj, obj.properties[metric_name]


def _sync_system_stats_property_runtime(prop, new_val: Union[int, float], source: str, changed) -> None:
    object.__setattr__(prop, "_PropertyManager__value", new_val)
    prop.source = source
    prop.changed = changed


def _apply_core_system_stats_delta(
    metric_name: str,
    delta: Union[int, float],
    *,
    source: str = "core",
) -> bool:
    """Atomically add delta in DB (row lock) and sync runtime cache."""
    if not delta:
        return False
    metric_source = source or SYSTEM_STATS_SOURCE
    _, prop = _get_system_stats_property_manager(metric_name)
    if prop is None or prop.value_id is None:
        return False

    from app.core.models.Clasess import Value, History

    new_val: Union[int, float]
    changed = get_now_to_utc()
    with _stats_apply_lock:
        with session_scope() as session:
            row = (
                session.query(Value)
                .filter(Value.id == prop.value_id)
                .with_for_update()
                .one_or_none()
            )
            if row is None:
                return False
            try:
                current_val = float(row.value or 0)
            except (TypeError, ValueError):
                current_val = 0.0
            new_val = current_val + float(delta)
            if abs(new_val - round(new_val)) < 1e-9:
                new_val = int(round(new_val))
            encoded = str(new_val)
            row.value = encoded
            row.changed = changed
            row.source = metric_source
            if prop.history and prop.history > 0:
                session.add(
                    History(
                        value_id=prop.value_id,
                        value=encoded,
                        added=changed,
                        source=metric_source,
                    )
                )
            session.commit()

    _sync_system_stats_property_runtime(prop, new_val, metric_source, changed)
    scheduleSystemStatsWsNotify(SYSTEM_STATS_OBJECT, metric_name, new_val)
    return True


def writeCoreSystemStatsMetric(
    metric_name: str,
    value: Any,
    *,
    description: str = "",
    history: int = 30,
    prop_type: PropertyType = PropertyType.Float,
    source: str = "core",
) -> bool:
    """Write core metric to `SystemStats.<metric_name>` with track_stats=False."""
    from .object import updateProperty
    if not _is_system_stats_enabled():
        return False
    full_name = f"{SYSTEM_STATS_OBJECT}.{metric_name}"
    metric_source = source or SYSTEM_STATS_SOURCE
    return updateProperty(full_name, value, source=metric_source, track_stats=False)


def incrementCoreSystemStatsMetric(
    metric_name: str,
    step: Union[int, float] = 1,
    *,
    description: str = "",
    history: int = 30,
    source: str = "core",
) -> bool:
    """Increment numeric core metric in `SystemStats.<metric_name>`."""
    if not _is_system_stats_enabled():
        return False
    if metric_name in _BUFFERED_CORE_METRICS:
        _core_stats_buffer.increment(metric_name, step)
        return True
    return _apply_core_system_stats_delta(metric_name, step, source=source)


def _is_system_stats_enabled() -> bool:
    global _system_stats_enabled_cache, _system_stats_enabled_cache_at
    now = time.monotonic()
    with _system_stats_enabled_cache_lock:
        if (
            _system_stats_enabled_cache is not None
            and (now - _system_stats_enabled_cache_at) < _SYSTEM_STATS_ENABLED_CACHE_TTL
        ):
            return _system_stats_enabled_cache
    value = _get_property_value_no_stats("SystemVar", "system_stats")
    enabled = value is True
    with _system_stats_enabled_cache_lock:
        _system_stats_enabled_cache = enabled
        _system_stats_enabled_cache_at = now
    return enabled


def _read_system_stats_property_value(property_name: str):
    return _get_property_value_no_stats(SYSTEM_STATS_OBJECT, property_name)


def _get_property_value_no_stats(object_name: str, property_name: str):
    try:
        from app.core.main.ObjectsStorage import objects_storage
        obj = objects_storage.getObjectByName(object_name)
        if not obj or property_name not in obj.properties:
            return None
        return obj.properties[property_name].getValue(track_stats=False)
    except Exception:
        return None