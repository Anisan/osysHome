import datetime
from dateutil import parser
import threading
import json
from sqlalchemy import update
from flask import render_template_string
from app.database import session_scope,row2dict
from app.core.main.PluginsHelper import plugins
from app.core.models.Clasess import Object, Property, Value, History
from app.core.lib.common import setTimeout
from app.core.lib.execute import execute_and_capture_output
from app.logging_config import getLogger
_logger = getLogger('object')

class PropertyManager():
    def __init__(self, property: Property, value: Value):
        self.property_id = property.id
        self.value_id = value.id if value else None
        self.name = property.name
        self.description = property.description
        self.object_id = None
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
            self.__value = self._decodeValue(value.value)
        self.count_read = 0
        self.count_write = 0
        self.readed = datetime.datetime.now()

    def _decodeValue(self, value):
        if value is None:
            return None
        converted_value = None
        # Конвертация строки в указанный тип
        try:
            if value == 'None':
                converted_value = None
            elif self.type == "int":
                converted_value = int(value)
            elif self.type == "float":
                converted_value = float(value)
            elif self.type == "str":
                converted_value = value
            elif self.type == "datetime":
                if isinstance(value, str):
                    converted_value = parser.parse(value)
                else:
                    converted_value = value
            elif self.type == "dict":
                converted_value = json.loads(value)
            elif self.type == "list":
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
            _logger.exception(ex, exc_info=True)
            converted_value = value
        return converted_value

    def _encodeValue(self):
        # TODO convert to string
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
                return value.strftime("%Y-%m-%d %H:%M:%S")
            elif self.type == "dict":
                return json.dumps(value)
            elif self.type == "list":
                return json.dumps(value)
            else:
                return value
        except Exception as ex:
            _logger.exception(ex, exc_info=True)
        return str(self.__value)

    def saveValue(self):
        try:
            with session_scope() as session:    # todo maybe use one session ??
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
                if self.history > 0:
                    hist = History()
                    hist.value_id = self.value_id
                    hist.added = self.changed
                    hist.value = stringValue
                    hist.source = self.source
                    session.add(hist)

                session.commit()
        except Exception as ex:
            _logger.exception(ex, exc_info=True)

    def setValue(self, value, source='', changed=None):
        
        self.__value = self._decodeValue(value)
        self.source = source
        if changed is not None:
            self.changed = changed
        else:
            now = datetime.datetime.now()
            self.changed = now

        # save Value To DB
        # self.saveValue()
        thread = threading.Thread(target=self.saveValue)
        thread.start()
        self.count_write = self.count_write + 1

    def getValue(self):
        self.readed = datetime.datetime.now()
        self.count_read = self.count_read + 1
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
            "changed": str(self.changed) if self.changed else None,
            "method": self.method,
            "linked": self.linked,
            "source": self.source,
            "type": self.type,
            "value": self.value if self.type != 'datetime' else str(self.value),
            #"count_read": self.count_read,
            #"count_write": self.count_write,
            #"readed": str(self.readed)
        }
    
    def __str__(self):
        return f"PropertyManager(name='{self.name}', description='{self.description}', value='{self.value}')"

    def __repr__(self):
        return self.__str__()

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
    
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            #"source": self.source,
            #"count_executed": self.count_executed,
            #"executed": str(self.executed) if self.executed else None,
            #"exec_params": self.exec_params,
            #"exec_result": self.exec_result
        }
    
    def __str__(self):
        return f"MethodManager(name='{self.name}', description='{self.description}')"

    def __repr__(self):
        return self.__str__()

class ObjectManager:
    """ Object manager
        Contain properties and methods
    """
    def __init__(self, obj: Object):
        self.object_id = obj.id
        self.name = obj.name
        self.description = obj.description
        self.template = obj.template
        self.properties = {}
        self.methods = {}

    def _addProperty(self, property: PropertyManager) -> None:
        property.object_id = self.object_id
        if property.value_id is None:
            with session_scope() as session:
                valRec = Value()
                valRec.object_id = property.object_id
                valRec.name = property.name
                session.add(valRec)
                session.commit()
                property.value_id = valRec.id
        self.properties[property.name] = property

    def setProperty(self, name:str, value, source:str=''):
        """ Set property value

        Args:
            name (str): property name
            value (str): property value
            source (str): source of the value

        """
        try:
            _logger.debug("ObjectManager::setProperty %s.%s - %s", self.name, name, str(value))
            if name not in self.properties:
                with session_scope() as session:
                    property_db = Property()
                    property_db.object_id = self.object_id
                    property_db.name = name
                    property_db.type = type(value).__name__
                    session.add(property_db)
                    session.commit()
                    prop = PropertyManager(property_db,None)
                    self._addProperty(prop)
            prop = self.properties[name]
            old = prop.getValue()
            prop.setValue(value, source)
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
                    # TODO get plugin
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

        except Exception as ex:
            _logger.exception(ex, exc_info=True)

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
                self.setProperty(name, value, source)
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
        if name in self.properties:
            prop = self.properties[name]
            return getattr(prop, data, None)
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
            prop = self.__dict__['properties'][name]
            return prop.value
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name, value):
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

            self.methods[name].source = source
            self.methods[name].executed = datetime.datetime.now()
            self.methods[name].exec_params = args
            self.methods[name].exec_result = output
            self.methods[name].count_executed = self.methods[name].count_executed + 1

            # send event to proxy
            for _,plugin in plugins.items():
                if 'proxy' in plugin["instance"].actions:
                    plugin["instance"].executedMethod(self.name, name)

            return output
        except Exception as ex:
            _logger.critical(ex, exc_info=True)     # TODO write adv info
            return str(ex)

    def render(self) -> str:
        """Render object template

        Returns:
            str: html view object
        """
        try:
            if self.template:
                return render_template_string(self.template, object=self)
            return ''
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
        src = f',"{source}"' if source else ',"Scheduler"'
        code = f'callMethod("{self.name}.{methodName}"{src})'
        setTimeout(self.name + "_" + methodName + "_timeout", code, timeout)

    def getHistory(self, name:str, dt_begin:datetime = None, dt_end:datetime = None, limit:int = None, order_desc: bool = False, func=None) -> list:
        """Get history of a property

        Args:
            name (str): Name property
            dt_begin (datetime, optional): Begin date. Defaults to None.
            dt_end (datetime, optional): End date. Defaults to None.
            limit (int, optional): Limit. Defaults to None.
            order_desc (bool, optional): Order desc. Defaults to False.
            func (function, optional): Function to apply to the data. Defaults to None.

        Returns:
            list: List of history
        """

        if name not in self.properties:
            return None
        prop:PropertyManager = self.properties[name]
        value_id = prop.value_id

        with session_scope() as session:
            result = History.getHistory(session, value_id, dt_begin,dt_end,limit,order_desc,row2dict)
            for item in result:
                item['value'] = prop._decodeValue(item["value"])
                del item["value_id"]
            if func:
                result = [func(r) for r in result]
            return result

    def getHistoryAggregate(self, name:str, dt_begin:datetime = None, dt_end:datetime = None, func:str = None):
        """Get aggregate history of a property

        Args:
            name (str): Name property
            dt_begin (datetime, optional): Begin date. Defaults to None.
            dt_end (datetime, optional): End date. Defaults to None.
            func (str, optional): Aggregate function (min,max,sum,avg,count). Defaults to None, return all aggregate value.

        Returns:
            any : Result function
        """
        if name not in self.properties:
            return None
        prop:PropertyManager = self.properties[name]
        value_id = prop.value_id

        with session_scope() as session:
            if func == 'count':
                result = History.get_count(session, value_id, dt_begin,dt_end)
                return result
            data = self.getHistory(name, dt_begin, dt_end)
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
            "template": self.template,
            "properties": properties_dict,
            "methods": methods_dict
        }

    def __str__(self):
        return f"ObjectManager(name='{self.name}', description='{self.description}')"

    def __repr__(self):
        return self.__str__()
