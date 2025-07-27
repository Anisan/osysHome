import datetime
import time
from enum import Enum
from dateutil import parser
import concurrent.futures
from threading import Lock
import json
from sqlalchemy import update, delete
from flask_login import current_user
from app.database import session_scope,row2dict, convert_utc_to_local, convert_local_to_utc, get_now_to_utc
from app.core.main.PluginsHelper import plugins
from app.core.models.Clasess import Object, Property, Value, History
from app.core.lib.common import setTimeout
from app.core.lib.execute import execute_and_capture_output
from app.logging_config import getLogger
_logger = getLogger('object')

# Глобальный пул потоков (максимум 20 одновременных задач)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
_executor_lock = Lock()

class TypeOperation(Enum):
    """ Type operation """
    Get = "get"
    Set = "set"
    Call = "call"
    Edit = "edit"

class PropertyManager():
    """
    Initializes an ObjectManager instance with the given parameters.

    Args:
        object_id (int): The ID of the object.
        property (Property): The property object containing property details.
        value (Value): The value object containing value details or None.

    Attributes:
        property_id: ID of the property.
        value_id: ID of the value if exists, otherwise None.
        name: Name of the property.
        description: Description of the property.
        object_id: ID of the object.
        history: History count of the property or 0 if not specified.
        changed: Timestamp when the value was changed, None if no value.
        method: Method associated with the property (initialized to None).
        linked: List of linked items if exists, None otherwise.
        source: Source of the value if exists, None otherwise.
        __value: Decoded value of the property.
        type: Type of the property.
        count_read: Count of read operations (initialized to 0).
        count_write: Count of write operations (initialized to 0).
        readed: Timestamp of when the property was last read (UTC).
    """
    def __init__(self, object_id:int, property: Property, value: Value):
        self.property_id = property.id
        self.value_id = value.id if value else None
        self.name = property.name
        self.description = property.description
        self.object_id = object_id
        self.history = property.history or 0
        self.changed = value.changed if value else None
        self.method = None
        self.linked = None
        self.source = value.source if value else None
        if value and value.linked:
            links = value.linked.split(',')
            self.linked = links
        self.__value = None
        self.type = property.type
        if value:
            self.__value = self._decodeValue(value.value, True)
        self.count_read = 0
        self.count_write = 0
        self.readed = get_now_to_utc()

    def _decodeValue(self, value, init=False):
        if value is None:
            return None
        converted_value = None
        # Конвертация строки в указанный тип
        try:
            if value == 'None':
                converted_value = None
            elif self.type == "int":
                if value != '':
                    converted_value = int(value)
                else:
                    converted_value = None
            elif self.type == "float":
                if value != '':
                    converted_value = float(value)
                else:
                    converted_value = None
            elif self.type == "str":
                converted_value = value
            elif self.type == "datetime":
                if isinstance(value, str):
                    converted_value = parser.parse(value)
                else:
                    converted_value = value
                if converted_value and not init:
                    converted_value = convert_local_to_utc(converted_value)
            elif self.type == "dict":
                if isinstance(value, dict):
                    converted_value = value
                else:
                    converted_value = json.loads(value)
            elif self.type == "list":
                if isinstance(value, list):
                    converted_value = value
                else:
                    converted_value = json.loads(value)
            elif self.type == "bool":
                if isinstance(value, str):
                    if value.lower() in ['true', '1', 't', 'y', 'yes', 'on']:
                        converted_value = True
                    elif value.lower() in ['false', '0', 'f', 'n', 'no', 'off']:
                        converted_value = False
                    else:
                        raise ValueError(f"Invalid boolean value: {value}")
                else:
                    converted_value = bool(value)
            else:
                converted_value = value
        except Exception as ex:
            _logger.error(
                f"Error in object (object_id={self.object_id}, name={self.name}, value={value}): {str(ex)}",
                exc_info=True
            )
            converted_value = value
        return converted_value

    def _encodeValue(self):
        # convert to string
        value = self.__value
        if value is None:
            return 'None'
        try:
            if self.type == "int":
                return str(value)
            elif self.type == "float":
                return str(value)
            elif self.type == "str":
                return str(value)
            elif self.type == "datetime":
                return value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            elif self.type == "dict":
                return json.dumps(value)
            elif self.type == "list":
                return json.dumps(value)
            else:
                return value
        except Exception as ex:
            _logger.exception(ex, exc_info=True)
        return str(self.__value)

    def saveValue(self, save_history:bool=None):
        try:
            with session_scope() as session:
                if self.value_id is None:
                    valRec = Value()
                    valRec.object_id = self.object_id
                    valRec.name = self.name
                    session.add(valRec)
                    session.commit()
                    self.value_id = valRec.id

                stringValue = self._encodeValue()
                if stringValue is None:
                    _logger.info(stringValue)

                sql = update(Value).where(Value.id == self.value_id).values(value=stringValue, changed=self.changed, source=self.source)
                session.execute(sql)

                # save history
                if (self.history > 0 and (save_history is None or save_history)) or (self.history < 0 and save_history is not None and save_history):
                    hist = History()
                    hist.value_id = self.value_id
                    hist.added = self.changed
                    hist.value = stringValue
                    hist.source = self.source
                    session.add(hist)

                session.commit()
        except Exception as ex:
            _logger.exception(ex, exc_info=True)

    def cleanHistory(self):
        with session_scope() as session:
            count = session.query(History).where(History.value_id == self.value_id).count()
            if (self.history != 0):
                period = abs(self.history)
                # clean history
                dt = get_now_to_utc() - datetime.timedelta(days=period)
                sql = delete(History).where(History.value_id == self.value_id, History.added < dt)
                result = session.execute(sql)
                deleted_count = result.rowcount
                session.commit()
                return deleted_count, count - deleted_count
            elif count > 0:
                sql = delete(History).where(History.value_id == self.value_id)
                result = session.execute(sql)
                deleted_count = result.rowcount
                session.commit()
                return deleted_count, count - deleted_count
            return 0, count

    def setValue(self, value, source='', changed=None, save_history:bool=None):

        self.__value = self._decodeValue(value)
        self.source = source
        username = getattr(current_user, 'username', None)
        if username:
            if self.source != '':
                self.source += ':'
            self.source += username
        if changed is not None:
            self.changed = changed
        else:
            now = get_now_to_utc()
            self.changed = now

        # save Value To DB
        # self.saveValue()
        def wrapper():
            try:
                self.saveValue(save_history)
            except Exception as ex:
                _logger.exception(f"Error saving value in thread: {str(ex)}")

        # Используем глобальный пул потоков вместо создания новых
        with _executor_lock:
            _executor.submit(wrapper)

        self.count_write = self.count_write + 1

    def getValue(self):
        self.readed = get_now_to_utc()
        self.count_read = self.count_read + 1
        if self.type == 'datetime' and self.__value:
            try:
                return convert_utc_to_local(self.__value)
            except Exception as ex:
                _logger.exception(ex)
        return self.__value

    @property
    def value(self):
        return self.getValue()

    @value.setter
    def value(self, value):
        self.setValue(value)

    def bindMethod(self, name):
        self.method = name

    def to_dict(self):
        return {
            "property_id": self.property_id,
            "value_id": self.value_id,
            "name": self.name,
            "description": self.description,
            "history": self.history,
            "changed": str(convert_utc_to_local(self.changed)) if self.changed else None,
            "method": self.method,
            "linked": self.linked,
            "source": self.source,
            "type": self.type,
            "value": self.value if self.type != 'datetime' else str(self.value),
            "count_read": self.count_read,
            "count_write": self.count_write,
            "readed": str(convert_utc_to_local(self.readed))
        }

    def __str__(self):
        return f"PropertyManager(name='{self.name}', description='{self.description}', value='{self.value}')"

    def __repr__(self):
        return self.__str__()

"""
Manages method information and execution tracking.

This class encapsulates information about methods, including their execution status and results.
It provides methods to convert the method data to a dictionary and string representations.

Attributes:
    methods (list): List of method dictionaries including parent methods.
    name (str): Name of the method (taken from the first method in the list).
    description (str): Description of the method (taken from the first method in the list).
    source (str): Source of the method (None by default).
    count_executed (int): Number of times the method has been executed.
    executed (datetime): Timestamp of last execution (None if never executed).
    exec_params (any): Parameters used in last execution.
    exec_result (any): Result from last execution.
    exec_time (int): Time taken for last execution (in milliseconds).
"""
class MethodManager():
    def __init__(self, methods):
        self.methods = methods  # include parents
        self.name = methods[0]["name"]
        self.description = methods[0]["description"]
        self.source = None
        self.count_executed = 0
        self.executed = None
        self.exec_params = None
        self.exec_result = None
        self.exec_time = None

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "methods": self.methods,
            "count_executed": self.count_executed,
            "executed": str(convert_utc_to_local(self.executed)) if self.executed else None,
            "exec_params": self.exec_params,
            "exec_result": self.exec_result,
            "exec_time": self.exec_time
        }

    def __str__(self):
        return f"MethodManager(name='{self.name}', description='{self.description}')"

    def __repr__(self):
        return self.__str__()

"""
Manages object properties and methods with permission control.

This class provides functionality to handle object properties and methods with
built-in permission checking. It maintains properties and methods dictionaries,
handles property value updates with history tracking, and performs permission
checks before allowing any operations.

Attributes:
    object_id: The ID of the managed object.
    name: The name of the managed object.
    description: Description of the managed object.
    properties: Dictionary of property managers.
    methods: Dictionary of method managers.
"""
class ObjectManager:
    """ Object manager
        Contain properties and methods
    """
    def __init__(self, obj: Object):
        object.__setattr__(self, "__inited", False)
        object.__setattr__(self, "__permissions", None)
        object.__setattr__(self, "__templates", {})
        self.object_id = obj.id
        self.name = obj.name
        self.description = obj.description
        self.properties = {}
        self.methods = {}

    def _addProperty(self, property: PropertyManager) -> None:
        if property.value_id is None:
            with session_scope() as session:
                valRec = Value()
                valRec.object_id = property.object_id
                valRec.name = property.name
                session.add(valRec)
                session.commit()
                property.value_id = valRec.id
        self.properties[property.name] = property

    def set_permission(self, permissions):
        object.__setattr__(self, "__permissions", permissions)
        object.__setattr__(self, "__inited", True)

    def _check_permissions(self, operation:TypeOperation, property_name:str=None, method_name:str=None):
        if not object.__getattribute__(self, "__inited"):
            return True

        name = object.__getattribute__(self, "name")

        if name == "_permissions" and operation == TypeOperation.Get:
            return True

        # permissions check
        username = getattr(current_user, 'username', None)
        if username is None:
            return True

        role = getattr(current_user, 'role', None)

        if role == 'root':
            return True

        _permissions = object.__getattribute__(self, "__permissions")
        if _permissions is None:
            if role in ["user","editor","admin"]:
                return True
            else:
                raise PermissionError(f"User {username}({role}) don't have permission to {operation.name} obj:{name} property:{property_name} method:{method_name} permissions:None")

        permissions = None

        if "self" in _permissions:
            permissions = _permissions["self"]

        if property_name:
            if "properties" in _permissions and property_name in _permissions["properties"]:
                permissions = _permissions["properties"][property_name]

        if method_name:
            if "methods" in _permissions and method_name in _permissions["methods"]:
                permissions = _permissions["methods"][method_name]

        if permissions:
            permissions = permissions.get(operation.value, None)

        if permissions:
            denied_users = permissions.get("denied_users",None)
            if denied_users:
                if username in denied_users or "*" in denied_users:
                    raise PermissionError(f"User {username}({role}) don't have permission to {operation.name} obj:{name} property:{property_name} method:{method_name} permissions:{json.dumps(permissions)}")
            access_users = permissions.get("access_users",None)
            if access_users:
                if username in access_users or "*" in access_users:
                    return True
            denied_roles = permissions.get("denied_roles",None)
            if denied_roles:
                if role in denied_roles or "*" in denied_roles:
                    raise PermissionError(f"User {username}({role}) don't have permission to {operation.name} obj:{name} property:{property_name} method:{method_name} permissions:{json.dumps(permissions)}")
            access_roles = permissions.get("access_roles",None)
            if access_roles:
                if role in access_roles or "*" in access_roles:
                    return True

        if role in ["user","editor","admin"]:
            return True

        raise PermissionError(f"User {username}({role}) don't have permission to {operation.name} obj:{name} property:{property_name} method:{method_name} permissions:{json.dumps(permissions)}")

    def setProperty(self, name:str, value, source:str='', save_history:bool=None):
        """ Set property value

        Args:
            name (str): property name
            value (str): property value
            source (str): source of the value
            save_history (bool): save history of the value (default is None)

        Returns:
            bool: Result
        """
        try:
            _logger.debug("ObjectManager::setProperty %s.%s - %s", self.name, name, str(value))
            self._check_permissions(TypeOperation.Set, name, None)

            if name not in self.properties:
                with session_scope() as session:
                    property_db = Property()
                    property_db.object_id = self.object_id
                    property_db.name = name
                    property_db.type = type(value).__name__
                    session.add(property_db)
                    session.commit()
                    prop = PropertyManager(self.object_id, property_db, None)
                    self._addProperty(prop)
            prop = self.properties[name]
            old = prop.getValue()
            prop.setValue(value, source, save_history=save_history)
            value = prop.getValue()
            if prop.method:
                args = {
                    'VALUE': value, 'NEW_VALUE': value, 'OLD_VALUE': old, 'PROPERTY': name, 'SOURCE': source,
                }
                self.callMethod(prop.method, args, source)
            # link
            if prop.linked:
                for link in prop.linked:
                    if link == source:
                        continue
                    # get plugin
                    if link in plugins:
                        plugin = plugins[link]
                        try:
                            plugin["instance"].changeLinkedProperty(self.name, name, value)
                        except Exception as e:
                            _logger.exception(e)

            # send event to proxy
            for _,plugin in plugins.items():
                if 'proxy' in plugin["instance"].actions:
                    plugin["instance"].changeProperty(self.name, name, value)
            return True
        except Exception as ex:
            _logger.exception(ex, exc_info=True)
            return False

    def updateProperty(self, name:str, value, source:str='') -> bool:
        """Update property

        Args:
            name (str): Name property
            value (_type_): New value
            source (str, optional): Source. Defaults to ''.

        Returns:
            bool: Result
        """

        try:
            # cast value
            if name in self.properties:
                prop = self.properties[name]
                value = prop._decodeValue(value)
            oldValue = self.getProperty(name)
            if oldValue != value:
                return self.setProperty(name, value, source)
            return True
        except Exception as ex:
            _logger.exception(ex, exc_info=True)
        return False

    def getProperty(self, name:str, data:str = 'value'):
        """Get value of property

        Args:
            name (str): Name property
            data (str, optional): Data type. Defaults to 'value'. (changed, source)

        Returns:
            any: Value
        """
        self._check_permissions(TypeOperation.Get, name, None)

        if name in self.properties:
            prop = self.properties[name]
            value = getattr(prop, data, None)
            if data == 'changed' and value:
                try:
                    return convert_utc_to_local(value)
                except Exception as ex:
                    _logger.exception(ex)
            return value
        return None

    def getChanged(self, name:str):
        """Get datetime changing property

        Args:
            name (str): name property

        Returns:
            datetime: Datetime changing property
        """
        return self.getProperty(name, 'changed')

    def __getattr__(self, name):
        if name in self.__dict__['properties']:
            if not self._check_permissions(TypeOperation.Get, name, None):
                raise (f"You don't have permission to get property {name}")
            prop = self.__dict__['properties'][name]
            return prop.value
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        if name not in ['properties', 'templates']:
            self._check_permissions(TypeOperation.Set, name, None)

        if name == "properties":
            super().__setattr__(name, value)
        elif "properties" in self.__dict__ and name in self.properties:
            self.setProperty(name,value)
        else:
            super().__setattr__(name, value)

    def _addMethod(self, method: MethodManager):
        self.methods[method.name] = method

    def _bindMethod(self, prop_name, method_name):
        if method_name not in self.methods:
            _logger.warning("Method %s does not exist.", method_name)
            return
        self.properties[prop_name].bindMethod(method_name)

    def callMethod(self, name, args=None, source:str = '') -> str:
        """Call a method on the object.
        Args:
            name (str): The name of the method to call.
            args (list): The arguments to pass to the method.
            source (str): The source of the call.
        Returns:
            str: The result of the method call.
        """
        if name not in self.methods:
            _logger.warning("Method %s does not exist.", name)
            return None
        
        start = time.perf_counter()

        self._check_permissions(TypeOperation.Call, None, name)

        try:
            variables = {
                'self': self,
                'params': args,
                'logger': _logger,
                'source': source,
                **vars(self)
            }
            methods = self.methods[name].methods
            output = ''
            for method in methods:
                res, error = execute_and_capture_output(method['code'],variables)
                if error:
                    output += "Error method in " + method['owner'] + "\n" + res
                    break
                if res:
                    output += res + "\n"

            username = getattr(current_user, 'username', None)
            if username:
                if source != '':
                    source += ':'
                source += username
            self.methods[name].source = source
            self.methods[name].executed = get_now_to_utc()
            self.methods[name].exec_params = args
            self.methods[name].exec_result = output
            self.methods[name].count_executed = self.methods[name].count_executed + 1

            end = time.perf_counter()
            self.methods[name].exec_time = int((end - start) * 1000)  # в миллисекунды

            # send event to proxy
            for _,plugin in plugins.items():
                if 'proxy' in plugin["instance"].actions:
                    plugin["instance"].executedMethod(self.name, name)

            return output
        except Exception as ex:
            _logger.critical(ex, exc_info=True)
            return str(ex)

    def _setTemplates(self, templates):
        object.__setattr__(self, "__templates", templates)

    def render(self) -> str:
        """Render object template

        Returns:
            str: html view object
        """
        try:
            result = ''

            templates = object.__getattribute__(self, "__templates")

            from jinja2 import Environment, DictLoader
            env = Environment(loader=DictLoader(
                templates
            ))
            from app.core.lib.object import getProperty
            env.globals.update(getProperty=getProperty)

            render_template = self.name
            if not templates.get(render_template):
                for parent in self.parents:
                    if templates.get(parent):
                        render_template = parent
                        break

            if templates.get(render_template):
                template = env.get_template(render_template)
                result = template.render(object=self)
            if result == 'None':
                result = ''
            return result
        except Exception as ex:
            _logger.error(ex, exc_info=True)
            return str(ex)

    def setPropertyTimeout(self, propName:str, value, timeout:int, source=''):
        """Set the value of a Property with a Timeout

        Args:
            propName (str): Name property
            value(Any): Value
            timeout(int): Timeout in sec
            source(str): Source
        """
        self._check_permissions(TypeOperation.Set, propName, None)

        src = f',"{source}"' if source else ',"Scheduler"'
        code = f'setProperty("{self.name}.{propName}","{str(value)}"{src})'
        setTimeout(self.name + "_" + propName + "_timeout", code, timeout)

    def updatePropertyTimeout(self, propName:str, value, timeout:int, source=''):
        """Update property by its name if value changed on timeout.

        Args:
            propName (str): Name property
            value(Any): Value
            timeout(int): Timeout in sec
            source(str): Source
        """
        self._check_permissions(TypeOperation.Set, propName, None)

        src = f',"{source}"' if source else ',"Scheduler"'
        code = f'updateProperty("{self.name}.{propName}","{str(value)}"{src})'
        setTimeout(self.name + "_" + propName + "_timeout", code, timeout)

    def callMethodTimeout(self, methodName:str, timeout:int, source:str = ''):
        """Call method with a timeout

        Args:
            methodName (str): Name method
            timeout (int): Timeout in sec
            source (str, optional): Source. Defaults to ''.
        """
        self._check_permissions(TypeOperation.Call, None, methodName)

        src = f',"{source}"' if source else ',"Scheduler"'
        code = f'callMethod("{self.name}.{methodName}"{src})'
        setTimeout(self.name + "_" + methodName + "_timeout", code, timeout)

    def getHistory(self, name:str, dt_begin:datetime = None, dt_end:datetime = None, limit:int = None, order_desc: bool = False, func=None) -> list:
        """Get history of a property

        Args:
            name (str): Name property
            dt_begin (datetime, optional): Begin local datetime. Defaults to None.
            dt_end (datetime, optional): End local datetime. Defaults to None.
            limit (int, optional): Limit. Defaults to None.
            order_desc (bool, optional): Order desc. Defaults to False.
            func (function, optional): Function to apply to the data. Defaults to None.

        Returns:
            list: List of history
        """
        self._check_permissions(TypeOperation.Get, name, None)

        if name not in self.properties:
            return None
        prop:PropertyManager = self.properties[name]
        value_id = prop.value_id

        dt_begin = convert_local_to_utc(dt_begin)
        dt_end = convert_local_to_utc(dt_end)

        with session_scope() as session:
            result = History.getHistory(session, value_id, dt_begin,dt_end,limit,order_desc,row2dict)
            for item in result:
                item['value'] = prop._decodeValue(item["value"])
                del item["value_id"]

            from app.core.lib.common import is_datetime_in_range
            if is_datetime_in_range(prop.changed, dt_begin, dt_end, True):
                changed = convert_utc_to_local(prop.changed)
                if result:
                    find = any(item.get("added") == changed for item in result)
                    if not find:
                        result.append({"value": prop.value, "added": changed, "source": prop.source})
                else:
                    result.append({"value": prop.value, "added": changed, "source": prop.source})
            if func:
                result = [func(r) for r in result]
            return result

    def getHistoryAggregate(self, name:str, dt_begin:datetime = None, dt_end:datetime = None, func:str = None):
        """Get aggregate history of a property

        Args:
            name (str): Name property
            dt_begin (datetime, optional): Begin local datetime. Defaults to None.
            dt_end (datetime, optional): End local datetime. Defaults to None.
            func (str, optional): Aggregate function (min,max,sum,avg,count). Defaults to None, return all aggregate value.

        Returns:
            any : Result function
        """
        self._check_permissions(TypeOperation.Get, name, None)

        if name not in self.properties:
            return None
        prop:PropertyManager = self.properties[name]
        value_id = prop.value_id

        with session_scope() as session:
            if func == 'count':
                dt_begin = convert_local_to_utc(dt_begin)
                dt_end = convert_local_to_utc(dt_end)
                result = History.get_count(session, value_id, dt_begin,dt_end)
                return result
            data = self.getHistory(name, dt_begin, dt_end)
            if not data:
                return None
            data = [item['value'] for item in data]
            if func == 'min':
                result = min(data)
            elif func == 'max':
                result = max(data)
            elif func == 'sum':
                result = sum(data)
            elif func == 'avg':
                result = sum(data) / len(data) if data else 0
            else:
                result = {
                    "count": len(data),
                    "min": min(data),
                    "max": max(data),
                    "sum": sum(data),
                    "avg": sum(data) / len(data) if data else 0
                }
            return result

    """
    Cleans the history of all properties in the object manager.

    Iterates over all properties and cleans their history, returning a count of deleted items
    and the remaining history for each property.

    Returns:
        dict: A dictionary with property names as keys and dictionaries as values.
              Each value dictionary contains:
                - "history": The remaining history of the property
                - "deleted": Count of deleted history items
                - "all": Total count of history items (deleted + remaining)
    """
    def cleanHistory(self):
        """Clean history of all properties"""
        count = {}
        for key, prop in self.properties.items():
            deleted_count, all = prop.cleanHistory()
            count[key] = {"history": prop.history, "deleted":deleted_count, "all": all}
        return count

    def getStats(self):
        stat_props = {}
        stat_methods = {}
        for name, prop in self.properties.items():
            from app.core.utils import truncate_string
            value = truncate_string(str(prop.value), 30)
            stat_props[name] = {
                'id': prop.property_id,
                'description': prop.description,
                'value': value,
                'source': prop.source,
                'count_read': prop.count_read,
                'count_write': prop.count_write,
                'last_read': prop.readed,
                'last_write': prop.changed,
            }
        for name, method in self.methods.items():
            stat_methods[name] = {
                'count_executed': method.count_executed,
                'last_executed': method.executed,
                'exec_time': method.exec_time,
                'source': method.source,
                'params': method.exec_params,
            }
        return {
            "stat_properties": stat_props,
            "stat_methods": stat_methods,
        }

    def to_dict(self):
        properties_dict = {name: prop.to_dict() for name, prop in self.properties.items()}
        methods_dict = {name: method.to_dict() for name, method in self.methods.items()}

        return {
            "name": self.name,
            "id": self.object_id,
            "description": self.description,
            "templates": object.__getattribute__(self, "__templates"),
            "properties": properties_dict,
            "methods": methods_dict,
            "parents": self.parents,
            "permissions": object.__getattribute__(self, "__permissions")
        }

    def __str__(self):
        return f"ObjectManager(name='{self.name}', description='{self.description}')"

    def __repr__(self):
        return self.__str__()
