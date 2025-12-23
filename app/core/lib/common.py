""" Common library """
import threading
from contextlib import contextmanager
import datetime
from typing import Optional, Union
from sqlalchemy import update, delete
import xml.etree.ElementTree as ET
from app.core.lib.execute import execute_and_capture_output
from app.logging_config import getLogger
from app.database import session_scope, row2dict, convert_local_to_utc, convert_utc_to_local, get_now_to_utc
from .crontab import nextStartCronJob
from .constants import CategoryNotify
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


def callPluginFunction(plugin: str, func: str, args):
    """Call plugin function

    Args:
        plugin (str): Name plugin
        func (str): Name function in plugin
        ars (dict): Arguments
    """
    if plugin not in plugins:
        return
    plugin_obj = plugins[plugin]["instance"]

    # Вызываем функцию по её текстовому названию
    if hasattr(plugin_obj, func):
        function = getattr(plugin_obj, func)
        try:
            function(**args)
        except Exception as ex:
            _logger.exception(ex)
    else:
        _logger.error("Function '%s' not found in plugin %s.", func, plugin)


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
            sql = update(Notify).where(Notify.id == notify_id).values(read=True)
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

def readNotifyAll(source: str):
    """Set read all notify for source

    Args:
        source (str): Source notify
    """
    with session_scope() as session:
        sql = update(Notify).where(Notify.source == source).values(read=True)
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
            "source": source,
        }
    }
    callPluginFunction("wsServer","notify", {"data":notify_data})


def getUrl(url) -> str:
    """Get content from URL

    Args:
        url (str): URL

    Returns:
        str: Content
    """
    import requests

    try:
        result = requests.get(url)
        return result.content
    except Exception as e:
        _logger.exception(e)
    return None

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
    check_dt: datetime.datetime,
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
