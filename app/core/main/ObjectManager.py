import datetime
from dateutil import parser
import threading
import json
from sqlalchemy import update
from flask import render_template_string
from app.database import session_scope
from app.core.main.PluginsHelper import plugins
from app.core.models.Clasess import Object, Property, Value, History
from app.core.lib.common import setTimeout
from app.logging_config import getLogger
_logger = getLogger('object')

class PropertyManager():
    def  __init__(self, property: Property, value: Value):
        self.__property_id = property.id
        self._value_id = value.id if value else None
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

    def _decodeValue(self, value):
        if  value == None: return None
        converted_value = None
         ## TODO cast type ??
        # Конвертация строки в указанный тип
        try:
            if self.type == "int":
                converted_value = int(value)
            elif self.type == "float":
                converted_value = float(value)
            elif self.type == "str":
                converted_value = value
            elif self.type == "datetime":
                if  isinstance(value, str):
                    converted_value = parser.parse(value)
                else:
                    converted_value = value
            elif self.type == "dict":
                converted_value = json.loads(value)
            elif self.type == "object":
                converted_value = json.loads(value)
            else:
                converted_value = value 
        except Exception as ex:
            _logger.exception(ex, exc_info=True)
            converted_value = value 
        return converted_value

    def _encodeValue(self):  
        # TODO convert to string
        value = self.__value
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
            elif self.type == "object":
                return json.dumps(value)
            else:
                return value 
        except Exception as ex:
            _logger.exception(ex, exc_info=True)
        return str(self.__value)

    def saveValue(self):
        try:
            with session_scope() as session: #todo maybe use one session ??
                if self._value_id == None:
                    valRec = Value()
                    valRec.object_id = self.object_id
                    valRec.name = self.name
                    session.add(valRec)
                    session.commit()
                    self._value_id = valRec.id

                stringValue = self._encodeValue()
                if stringValue == None:
                    _logger.info(stringValue)
                
                sql = update(Value).where(Value.id == self._value_id).values(value = stringValue,changed = self.changed, source = self.source)
                session.execute(sql)
                
                # save history
                if self.history > 0:
                    hist = History()
                    hist.value_id = self._value_id
                    hist.added = self.changed
                    hist.value = stringValue
                    hist.source = self.source
                    session.add(hist)
                
                session.commit()
        except Exception as ex:
            _logger.exception(ex, exc_info=True)

    def setValue(self, value, source='', changed = None):
        
        self.__value = self._decodeValue(value)
        self.source = source
        if changed !=None:
            self.changed = changed
        else:
            now = datetime.datetime.now()
            self.changed = now

        # save Value To DB
        #self.saveValue()
        thread = threading.Thread(target=self.saveValue)
        thread.start()

    def getValue(self):
        return self.__value
    
    @property
    def value(self):
        return self.getValue()
    
    @value.setter
    def value(self, value):
        self.setValue(value)

    def bindMethod(self, name):
        self.method = name


class MethodManager():
    def  __init__(self, methods):
        self.name = methods[0].name
        self.description = methods[0].description
        code = ""
        for m in methods:
            if m.code:
                code+="\n"+m.code
        self.code = code

class ObjectManager:
    """ Object manager
        Contain properties and methods
    """
    def __init__(self, obj: Object):
        self.__object = obj
        self.name = obj.name
        self.description = obj.description
        self.template = obj.template
        self.properties = {}
        self.methods = {}

    def _addProperty(self, property: PropertyManager) -> None:
        property.object_id = self.__object.id
        if property._value_id == None:
            with session_scope() as session:
                valRec = Value()
                valRec.object_id = property.object_id
                valRec.name = property.name
                session.add(valRec)
                session.commit()
                property._value_id = valRec.id
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
                    property_db.object_id = self.__object.id
                    property_db.name = name
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
                    if link == source: continue
                    # TODO get plugin
                    if link in plugins:
                        plugin = plugins[link]
                        try:
                            plugin["instance"].changeLinkedProperty(self.name, name, value)
                        except Exception as e:
                            _logger.exception(e)

            # TODO send to WS
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
            code = self.methods[name].code
            code = "from app.core.lib.common import *\nfrom app.core.lib.object import *\nfrom app.core.lib.cache import *\n" + code ## TODO append common libs
            #exec(code, globals(), {'self': self, 'params':args, **vars(self)})
            # Создаем контекст, в который передаем logger и другие переменные
            exec_globals = globals().copy()
            exec_locals = {
                'self': self,
                'params': args,
                'logger': _logger,
                'source': source,
                **vars(self)
            }

            from io import StringIO
            import sys
            old_stdout = sys.stdout
            redirected_output = sys.stdout = StringIO()
            try:
                # Выполняем код модуля в контексте с logger
                exec(code, exec_globals, exec_locals)
            except:
                raise 
            finally: # !
                sys.stdout = old_stdout # !

            return redirected_output.getvalue()
        except Exception as ex:
            _logger.critical(ex, exc_info=True) # TODO write adv info
            return str(ex)

    def render(self) -> str:
        """Render object template

        Returns:
            str: html view object
        """
        return render_template_string(self.template, object=self)
    
    def setPropertyTimeout(self, propName:str, value, timeout:int, source=''):
        """Set the value of a Property with a Timeout

        Args:
            propName (str): Name property
            value(Any): Value
            timeout(int): Timeout in sec
            source(str): Source
        """
        code = "setProperty('"+self.name+"."+propName+"','"+str(value)+"','"+source+"')"
        setTimeout(self.name+"_"+propName+"_timeout", code, timeout)

    def updatePropertyTimeout(self, propName:str, value, timeout:int, source=''):
        """Update property by its name if value changed on timeout.

        Args:
            propName (str): Name property
            value(Any): Value
            timeout(int): Timeout in sec
            source(str): Source
        """
        code = "updateProperty('"+self.name+"."+propName+"','"+str(value)+"','"+source+"')"
        setTimeout(self.name+"_"+propName+"_timeout", code, timeout)
   
    def callMethodTimeout(self, methodName:str, timeout:int, source:str = ''):
        """Call method with a timeout

        Args:
            methodName (str): Name method
            timeout (int): Timeout in sec
            source (str, optional): Source. Defaults to ''.
        """
        code = "callMethod('"+self.name+"."+methodName+"','"+source+"')"
        setTimeout(self.name+"_"+methodName+"_timeout", code, timeout)
