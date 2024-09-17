""" Common library """

import datetime
from sqlalchemy import update, delete
import xml.etree.ElementTree as ET
from app.core.lib.execute import execute_and_capture_output
from app.logging_config import getLogger
from app.database import session_scope, row2dict
from .crontab import nextStartCronJob
from .constants import CategoryNotify
from ..main.PluginsHelper import plugins
from ..models.Tasks import Task
from ..models.Plugins import Notify

_logger = getLogger("common")


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
    try:
        with session_scope() as session:
            task = session.query(Task).filter(Task.name == name).one_or_none()
            if not task:
                task = Task()
                task.name = name
                session.add(task)
            task.code = code
            task.runtime = dt
            task.expire = dt + datetime.timedelta(seconds=expire)
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
    try:
        with session_scope() as session:
            dt = nextStartCronJob(crontab)
            task = session.query(Task).filter(Task.name == name).one_or_none()
            if not task:
                task = Task()
                task.name = name
                session.add(task)
            task.code = code
            task.runtime = dt
            task.expire = dt + datetime.timedelta(1800)
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


def clearScheduledJob(name: str):
    """Clear jobs contains name

    Args:
        name (str): Name for search
    """
    with session_scope() as session:
        sql = delete(Task).where(Task.name.like(name))
        session.execute(sql)
        session.commit()


def deleteScheduledJob(id: int):
    """Delete job by id

    Args:
        id (int): ID job
    """
    with session_scope() as session:
        sql = delete(Task).where(Task.id == id)  # todo
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
    res = addScheduledJob(
        name, code, datetime.datetime.now() + datetime.timedelta(seconds=timeout)
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
    for _, plugin in plugins.items():
        if "say" in plugin["instance"].actions:
            try:
                plugin["instance"].say(message, level, args)
            except Exception as ex:
                _logger.exception(ex)


def playSound(file_name: str, level: int = 0):
    """Play sound

    Args:
        file_name (_type_): Path media file
        level (int, optional): Level. Defaults to 0.
    """
    for _, plugin in plugins.items():
        if "playsound" in plugin["instance"].actions:
            try:
                plugin["instance"].playSound(file_name, level)
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
    with session_scope() as session:
        notify = session.query(Notify).filter(Notify.name == name, Notify.description == description, Notify.read == False).one_or_none() # noqa
        if notify:
            notify.count = notify.count + 1
        else:
            notify = Notify()
            notify.name = name
            notify.description = description
            notify.category = category
            notify.source = source
            session.add(notify)
    # todo send to websocket
    #callPluginFunction()


def readNotify(notify_id: int):
    """Set read for notify

    Args:
        notify_id (int): ID notify
    """
    with session_scope() as session:
        sql = update(Notify).where(Notify.id == notify_id).values(read=True)
        session.execute(sql)
        session.commit()
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
