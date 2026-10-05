"""Shared helpers for tasks, plugins, notifications, HTTP, and system stats."""
import json
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
from app.database import session_scope, row2dict, convert_local_to_utc, convert_utc_to_local, get_now_to_utc, get_default_timezone, parse_int_id
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
_poolNotify = MonitoredThreadPool(thread_name_prefix="notify")

# Словарь для хранения блокировок, по одной на каждое имя задачи
_task_locks = {}
_task_locks_lock = threading.RLock()

@contextmanager
def get_task_lock(name: str):
    """Acquire a per-task-name lock for scheduled job mutations.

    Args:
        name (str): Task name used as the lock key.

    Yields:
        None: While the lock is held.
    """
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
    """Create or update a one-shot scheduled task.

    Args:
        name (str): Unique task name.
        code (str): Python code to run.
        dt (datetime.datetime): Local start time for the job.
        expire (int, optional): Seconds after start when the job expires.
            Defaults to 1800.

    Returns:
        Optional[int]: Task id on success, or ``None`` on error.
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
    """Create or update a recurring cron task.

    Args:
        name (str): Unique task name.
        code (str): Python code to run.
        crontab (str, optional): Cron schedule expression. Defaults to
            ``'* * * * *'``.

    Returns:
        Optional[int]: Task id on success, or ``None`` on error.
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
                # Cron wall time is server DEFAULT_TIMEZONE; store UTC in DB.
                utc_dt = convert_local_to_utc(dt, timezone=get_default_timezone())
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
    """Load a task row by name.

    Args:
        name (str): Task name.

    Returns:
        Optional[dict]: Task fields as a dict, or ``None`` if not found.
    """
    with session_scope() as session:
        job = session.query(Task).filter(Task.name == name).one_or_none()
        if job:
            return row2dict(job)
        return None

def getJobs(query: str) -> list:
    """Find tasks whose names match a SQL ``LIKE`` pattern.

    Args:
        query (str): Pattern passed to ``Task.name.like`` (include ``%`` wildcards).

    Returns:
        list: List of task dicts; empty if none match.
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
    """Delete tasks whose names match a SQL ``LIKE`` pattern.

    Args:
        name (str): Pattern passed to ``Task.name.like``.
    """
    with get_task_lock(name):
        with session_scope() as session:
            sql = delete(Task).where(Task.name.like(name))
            session.execute(sql)
            session.commit()

def setTimeout(name: str, code: str, timeout: int = 0):
    """Schedule code to run after a delay.

    Args:
        name (str): Task name for the delayed run.
        code (str): Python code to execute.
        timeout (int, optional): Delay in seconds from now. Defaults to 0.

    Returns:
        Optional[int]: Scheduled task id from ``addScheduledJob``, or ``None``.
    """
    local_dt = convert_utc_to_local(get_now_to_utc())
    res = addScheduledJob(
        name, code, local_dt + datetime.timedelta(seconds=timeout)
    )
    return res


def clearTimeout(name: str):
    """Remove a delayed task by name (same as ``clearScheduledJob``).

    Args:
        name (str): Task name pattern to delete.
    """
    clearScheduledJob(name)


def enableJob(name: str) -> bool:
    """Activate a task by name.

    Args:
        name (str): Task name.

    Returns:
        bool: ``True`` if the task existed and was enabled, else ``False``.
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
    """Deactivate a task by name.

    Args:
        name (str): Task name.

    Returns:
        bool: ``True`` if the task existed and was disabled, else ``False``.
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
    """Return a loaded plugin instance by folder name.

    Args:
        name (str): Plugin name (registry key).

    Returns:
        Optional[Any]: Plugin instance, or ``None`` if not loaded.
    """
    if name not in plugins:
        return None
    return plugins[name]["instance"]

def getModulesByAction(action: str):
    """List plugin instances that advertise a given action.

    Args:
        action (str): Action name (e.g. ``say``, ``notify``).

    Returns:
        list: Plugin instances whose ``actions`` include ``action``.
    """
    return [module["instance"] for _, module in plugins.items() if action in module["instance"].actions]


def callPluginFunction(plugin: str, func: str, args=None):
    """Call a public method on a loaded plugin instance.

    Args:
        plugin (str): Plugin name (folder name), e.g. ``YandexDevices``.
        func (str): Method name on the plugin class.
        args (Optional[dict]): Keyword arguments for the method.

    Returns:
        Optional[Any]: Plugin method return value, or ``None`` if the plugin or
        method is missing or the call raised an exception.
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
    """Broadcast text-to-speech to plugins with the ``say`` action.

    Args:
        message (str): Text to speak.
        level (int, optional): Priority or volume level (plugin-specific).
            Defaults to 0.
        args (Optional[dict]): Extra options; ``source`` defaults to
            ``osysHome``.
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
    """Play a media file on plugins with the ``playsound`` action.

    Args:
        file_name (str): Path or URL of the media file.
        level (int, optional): Priority or volume level (plugin-specific).
            Defaults to 0.
        args (Optional[dict]): Extra options passed to each plugin.
    """
    modules_with_playsound = getModulesByAction("playsound")
    for plugin in modules_with_playsound:
        try:
            _poolPlaysound.submit(plugin.playSound, f"playsound_{plugin.name}", file_name, level, args)
        except Exception as ex:
            _logger.exception(ex)


def _normalize_notify_params(params: Any) -> Optional[dict]:
    """Coerce notification ``params`` to a dict or ``None``."""
    if params is None:
        return None
    if isinstance(params, dict):
        return params
    if isinstance(params, str) and params.strip():
        try:
            parsed = json.loads(params)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _serialize_notify_params(params: Any) -> Optional[str]:
    """Serialize notification params to a JSON string for storage."""
    normalized = _normalize_notify_params(params)
    if not normalized:
        return None
    return json.dumps(normalized, ensure_ascii=False)


def notify_to_dict(notify: Notify) -> dict:
    """Serialize a ``Notify`` model row to a dict for API/WebSocket payloads.

    Args:
        notify (Notify): ORM notification instance.

    Returns:
        dict: Row fields with ``category`` as a name string and ``params`` as a dict.
    """
    data = row2dict(notify)
    data["category"] = notify.category.name if notify.category else "Info"
    data["params"] = _normalize_notify_params(data.get("params")) or {}
    return data


def addNotify(
    name: str,
    description: str = "",
    category: CategoryNotify = CategoryNotify.Info,
    source="",
    params: Optional[dict] = None,
):
    """Create or bump an in-app notification and notify plugins.

    Args:
        name (str): Short notification title or text.
        description (str, optional): Longer body text. Defaults to ``""``.
        category (CategoryNotify, optional): Severity/category. Defaults to
            ``CategoryNotify.Info``.
        source (str, optional): Originating plugin or module name. Defaults to
            ``""``.
        params (Optional[dict]): Extra payload (url, detail, error, image, …).
    """
    notify_id = None
    notify_count = 1
    params_json = _serialize_notify_params(params)
    with session_scope() as session:
        notify = session.query(Notify).filter(Notify.name == name, Notify.description == description, Notify.read == False).first() # noqa
        if notify:
            notify.count = (notify.count if notify.count else 0) + 1
            notify.last_updated = get_now_to_utc()
            if params_json is not None:
                notify.params = params_json
            notify_id = notify.id
            notify_count = notify.count
            session.commit()
        else:
            notify = Notify()
            notify.name = name
            notify.description = description
            notify.category = category
            notify.source = source
            notify.params = params_json
            notify.created = get_now_to_utc()
            notify.last_updated = get_now_to_utc()
            notify.count = 1
            session.add(notify)
            session.flush()
            notify_id = notify.id
            notify_count = 1

    notify_params = _normalize_notify_params(params) or {}
    from .object import setProperty
    data = {
        "name": name,
        "description": description,
        "category": category.value,
        "source": source,
        "params": notify_params,
    }
    setProperty("SystemVar.LastNotify", data, source)
    setProperty("SystemVar.UnreadNotify", True, source)

    _dispatchNotify({
        "operation": "new_notify",
        "data": {
            "id": notify_id,
            "name": name,
            "description": description,
            "category": category.value if hasattr(category, "value") else category,
            "source": source,
            "count": notify_count,
            "params": notify_params,
        },
    })


def _dispatchNotify(data: dict):
    """Submit ``notify`` payloads to plugins with the ``notify`` action."""
    for plugin in getModulesByAction("notify"):
        try:
            _poolNotify.submit(plugin.notify, f"notify_{plugin.name}", data)
        except Exception as ex:
            _logger.exception(ex)


def readNotify(notify_id: int):
    """Mark a single notification as read.

    Args:
        notify_id (int): Notification database id.

    Returns:
        Optional[bool]: ``True`` if the id was valid and processing ran; otherwise ``None``.
    """
    notify_id = parse_int_id(notify_id)
    if notify_id is None:
        return

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

    _dispatchNotify({
        "operation": "read_notify",
        "data": {
            "id": notify_id,
            "source": notify_source or "",
        },
    })

    return True

def getPluginModuleNames() -> set:
    """Return names of plugins loaded in the current process.

    Returns:
        set[str]: Plugin registry keys.
    """
    return {name for name in plugins.keys() if name}


def readNotifyAll(source: Optional[str] = None, control_panel: bool = False):
    """Mark multiple notifications as read.

    Args:
        source (Optional[str]): When set, only notifications with this ``source``.
            If ``None`` or empty (and ``control_panel`` is false), marks all as read.
        control_panel (bool): If ``True``, marks notifications whose source is not a
            loaded plugin module (control-panel / system sources), ignoring ``source``.
    """
    with session_scope() as session:
        if control_panel:
            from sqlalchemy import or_

            module_names = getPluginModuleNames()
            if module_names:
                sql = (
                    update(Notify)
                    .where(
                        or_(
                            Notify.source.is_(None),
                            Notify.source == "",
                            Notify.source.notin_(list(module_names)),
                        )
                    )
                    .values(read=True, read_date=get_now_to_utc())
                )
            else:
                # Нет известных модулей — не трогаем module-like, отмечаем только «системные»
                sql = (
                    update(Notify)
                    .where(
                        or_(
                            Notify.source.is_(None),
                            Notify.source == "",
                            Notify.source.in_(["admin", "osysHome", "core"]),
                        )
                    )
                    .values(read=True, read_date=get_now_to_utc())
                )
            event_source = "control_panel"
        elif source:
            sql = update(Notify).where(Notify.source == source).values(read=True, read_date=get_now_to_utc())
            event_source = source
        else:
            # Если source не указан, отмечаем все уведомления
            sql = update(Notify).values(read=True, read_date=get_now_to_utc())
            event_source = "all"
        session.execute(sql)
        session.commit()

        findUnread = session.query(Notify).filter(Notify.read == False).first()  # noqa
        from .object import updateProperty
        if findUnread:
            updateProperty("SystemVar.UnreadNotify", True)
        else:
            updateProperty("SystemVar.UnreadNotify", False)

    _dispatchNotify({
        "operation": "read_notify_all",
        "data": {
            "source": event_source,
        },
    })


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
    """Perform an HTTP request and return the response body.

    Args:
        url (str): Request URL.
        method (str, optional): HTTP method (GET, POST, PUT, PATCH, DELETE, …).
            Defaults to ``"GET"``.
        params (Optional[dict]): Query string parameters.
        headers (Optional[dict]): Request headers.
        json_data (Optional[dict]): JSON request body.
        data (Optional[dict]): Form or raw request body.
        cookies (Optional[dict]): Cookies as ``{name: value}``.
        timeout (Optional[float]): Timeout in seconds; defaults to
            ``Config.HTTP_REQUEST_TIMEOUT``.

    Returns:
        Optional[bytes]: Response content, or ``None`` on error.
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
    """Perform an HTTP GET via ``requestUrl``.

    Args:
        url (str): Request URL.
        params (Optional[dict]): Query string parameters.
        headers (Optional[dict]): Request headers.
        cookies (Optional[dict]): Cookies as ``{name: value}``.
        timeout (Optional[float]): Timeout in seconds.

    Returns:
        Optional[bytes]: Response content, or ``None`` on error.
    """
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
    """Perform an HTTP POST via ``requestUrl``.

    Args:
        url (str): Request URL.
        params (Optional[dict]): Query string parameters.
        headers (Optional[dict]): Request headers.
        json_data (Optional[dict]): JSON request body.
        data (Optional[dict]): Form or raw request body.
        cookies (Optional[dict]): Cookies as ``{name: value}``.
        timeout (Optional[float]): Timeout in seconds.

    Returns:
        Optional[bytes]: Response content, or ``None`` on error.
    """
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
    """Perform an HTTP PUT via ``requestUrl``.

    Args:
        url (str): Request URL.
        params (Optional[dict]): Query string parameters.
        headers (Optional[dict]): Request headers.
        json_data (Optional[dict]): JSON request body.
        data (Optional[dict]): Form or raw request body.
        cookies (Optional[dict]): Cookies as ``{name: value}``.
        timeout (Optional[float]): Timeout in seconds.

    Returns:
        Optional[bytes]: Response content, or ``None`` on error.
    """
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
    """Perform an HTTP PATCH via ``requestUrl``.

    Args:
        url (str): Request URL.
        params (Optional[dict]): Query string parameters.
        headers (Optional[dict]): Request headers.
        json_data (Optional[dict]): JSON request body.
        data (Optional[dict]): Form or raw request body.
        cookies (Optional[dict]): Cookies as ``{name: value}``.
        timeout (Optional[float]): Timeout in seconds.

    Returns:
        Optional[bytes]: Response content, or ``None`` on error.
    """
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
    """Perform an HTTP DELETE via ``requestUrl``.

    Args:
        url (str): Request URL.
        params (Optional[dict]): Query string parameters.
        headers (Optional[dict]): Request headers.
        cookies (Optional[dict]): Cookies as ``{name: value}``.
        timeout (Optional[float]): Timeout in seconds.

    Returns:
        Optional[bytes]: Response content, or ``None`` on error.
    """
    return requestUrl(
        url, method="DELETE", params=params, headers=headers, cookies=cookies, timeout=timeout
    )


def sendWebsocket(command: str, data: any, client_id:str=None) -> bool:
    """Send a command to the WebSocket server plugin.

    Args:
        command (str): Command name.
        data (Any): Payload for the command.
        client_id (Optional[str]): Target client id; ``None`` broadcasts to all.

    Returns:
        bool: ``True`` if the plugin handled the send, else ``False``.
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
    """Push typed data to connected WebSocket clients.

    Args:
        typeData (str): Message type identifier.
        data (Any): Payload to send.

    Returns:
        bool: ``True`` if the plugin handled the send, else ``False``.
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
    """Parse XML text into a nested dictionary.

    Args:
        xml_data (str): XML document as a string.

    Returns:
        dict: Root tag mapped to the parsed tree (attributes use ``@`` prefixes).
    """
    def recursive_dict(element):
        """Walk one ElementTree node into a tag/value pair."""
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
    """Execute a snippet of Python code in a restricted context.

    Args:
        code (str): Python source to run.
        args (Optional[dict]): Value bound as ``params`` in the execution namespace.

    Returns:
        tuple: ``(output, success)`` where ``output`` is captured stdout or an
        error string, and ``success`` is ``False`` if execution failed.
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
    """Check whether a datetime falls within an optional bounded range.

    All datetimes are normalized to naive UTC before comparison.

    Args:
        check_dt (Optional[datetime.datetime]): Value to test; ``None`` yields
            ``False``.
        start_dt (Optional[datetime.datetime]): Range start; ``None`` means
            unbounded below.
        end_dt (Optional[datetime.datetime]): Range end; ``None`` means unbounded
            above.
        inclusive (Union[bool, str], optional): Boundary inclusion: ``True``
            (default) both ends closed; ``False`` both open; ``"left"`` /
            ``"right"`` half-open intervals.

    Returns:
        bool: ``True`` if ``check_dt`` lies in the range per ``inclusive``.
    """
    # Нормализуем все даты к наивному UTC, чтобы избежать ошибок сравнения
    def _to_naive_utc(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
        """Convert aware datetimes to naive UTC; pass through naive values."""
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
    """Normalize a gender value to ``male``, ``female``, or ``unknown``.

    Strings are stripped and case-folded (English and Russian synonyms supported).
    Integer ``1`` and ``True`` map to male; ``0`` maps to female; ``False``,
    ``None``, and empty strings map to unknown.

    Args:
        gender (Any): Raw gender from config, speech, or user input.

    Returns:
        GenderKey: One of ``'male'``, ``'female'``, or ``'unknown'``.
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
    """Append gender-specific suffixes to a word stem (e.g. Russian agreement).

    Returns ``base + male_end``, ``base + female_end``, or ``base + default_end``
    depending on ``normalize_gender(gender)``.

    Args:
        gender (Any): Gender input (see ``normalize_gender``).
        base (str): Word stem without the inflection suffix.
        male_end (str): Suffix for male gender.
        female_end (str): Suffix for female gender.
        default_end (str, optional): Suffix when gender is unknown. Defaults to
            ``''``.

    Returns:
        str: ``base`` concatenated with the chosen suffix.

    Example:
        ``inflect_by_gender('female', 'готов', '', 'а')`` → ``'готова'``.
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
    """Register a plugin metric property on ``SystemStats`` for event-driven writes.

    Args:
        plugin_name (str): Plugin folder name.
        metric_name (str): Logical metric name (sanitized for the property key).
        description (str, optional): Human-readable description. Defaults to
            ``"{plugin_name}: {metric_name}"`` when empty.
        history (int, optional): History retention days for the property.
            Defaults to 30.
        prop_type (PropertyType, optional): Stored value type. Defaults to
            ``PropertyType.Float``.

    Returns:
        str: Property key only (without the ``SystemStats.`` prefix).
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
    """Write a plugin metric to ``SystemStats`` with ``track_stats=False``.

    Registers the property if needed. No-op when system stats are disabled.

    Args:
        plugin_name (str): Plugin folder name.
        metric_name (str): Logical metric name.
        value (Any): Value to store.
        description (str, optional): Property description for registration.
        history (int, optional): History retention when registering. Defaults to 30.
        prop_type (PropertyType, optional): Value type when registering.
        source (str, optional): Change source; defaults to
            ``system_stats:{plugin_name}``.

    Returns:
        bool: ``True`` if the write succeeded, else ``False``.
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
    """Increment a numeric plugin metric with ``track_stats=False``.

    Args:
        plugin_name (str): Plugin folder name.
        metric_name (str): Logical metric name.
        step (Union[int, float], optional): Delta to add. Defaults to 1.
        description (str, optional): Property description when registering.
        history (int, optional): History retention when registering. Defaults to 30.
        source (str, optional): Change source for the write.

    Returns:
        bool: ``True`` if the updated value was written, else ``False``.
    """
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
    """No-op; metric keys remain on the ``SystemStats`` object.

    Args:
        plugin_name (str): Plugin folder name (unused).
        metric_name (str): Logical metric name (unused).
    """
    # No in-memory registry anymore; metric keys remain in SystemStats object.
    return None


def unregisterSystemStatsPlugin(plugin_name: str) -> None:
    """No-op in event-driven mode (no in-process metric registry).

    Args:
        plugin_name (str): Plugin folder name (unused).
    """
    return None


def _system_stats_metric_key(plugin_name: str, metric_name: str) -> str:
    """Build the ``SystemStats`` property key for a plugin metric."""
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
        """Add ``step`` to a pending in-memory delta for ``metric_name``."""
        with self._lock:
            self._pending[metric_name] = self._pending.get(metric_name, 0) + step

    def flush(self) -> None:
        """Apply pending core metric deltas to the database."""
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
    """Queue a debounced WebSocket property update for ``SystemStats``.

    Args:
        object_name (str): Object name (typically ``SystemStats``).
        property_name (str): Property name to push.
        value (Any): Latest value to send after debounce.
    """
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
    """Send all pending debounced ``SystemStats`` WebSocket updates."""
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
    """Flush buffered core metric deltas (invoked from the BatchWriter tick)."""
    _core_stats_buffer.flush()


def invalidateSystemStatsEnabledCache() -> None:
    """Clear the cached ``SystemVar.system_stats`` enabled flag."""
    global _system_stats_enabled_cache
    with _system_stats_enabled_cache_lock:
        _system_stats_enabled_cache = None


def _get_system_stats_property_manager(metric_name: str):
    """Return ``(SystemStats object, property manager)`` or ``(None, None)``."""
    from app.core.main.ObjectsStorage import objects_storage
    obj = objects_storage.getObjectByName(SYSTEM_STATS_OBJECT)
    if not obj or metric_name not in obj.properties:
        return None, None
    return obj, obj.properties[metric_name]


def _sync_system_stats_property_runtime(prop, new_val: Union[int, float], source: str, changed) -> None:
    """Update in-memory property state after a DB write."""
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
    """Write a core metric to ``SystemStats.<metric_name>`` with ``track_stats=False``.

    Args:
        metric_name (str): Property name under ``SystemStats``.
        value (Any): Value to store.
        description (str, optional): Unused; kept for API symmetry with plugin metrics.
        history (int, optional): Unused; kept for API symmetry.
        prop_type (PropertyType, optional): Unused; kept for API symmetry.
        source (str, optional): Change source; defaults to ``core``.

    Returns:
        bool: ``True`` if the write succeeded, else ``False``.
    """
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
    """Increment a numeric core metric on ``SystemStats``.

    High-frequency metrics may be buffered in memory before a DB flush.

    Args:
        metric_name (str): Property name under ``SystemStats``.
        step (Union[int, float], optional): Delta to add. Defaults to 1.
        description (str, optional): Unused; kept for API symmetry.
        history (int, optional): Unused; kept for API symmetry.
        source (str, optional): Change source for non-buffered increments.

    Returns:
        bool: ``True`` if buffered or applied, else ``False``.
    """
    if not _is_system_stats_enabled():
        return False
    if metric_name in _BUFFERED_CORE_METRICS:
        _core_stats_buffer.increment(metric_name, step)
        return True
    return _apply_core_system_stats_delta(metric_name, step, source=source)


def _is_system_stats_enabled() -> bool:
    """Return whether ``SystemVar.system_stats`` is enabled (short TTL cache)."""
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
    """Read a ``SystemStats`` property without recording stats traffic."""
    return _get_property_value_no_stats(SYSTEM_STATS_OBJECT, property_name)


def _get_property_value_no_stats(object_name: str, property_name: str):
    """Read a property value from runtime cache with ``track_stats=False``."""
    try:
        from app.core.main.ObjectsStorage import objects_storage
        obj = objects_storage.getObjectByName(object_name)
        if not obj or property_name not in obj.properties:
            return None
        return obj.properties[property_name].getValue(track_stats=False)
    except Exception:
        return None