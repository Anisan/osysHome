"""Object library"""
import threading
import datetime
import json
from sqlalchemy import delete
from app.core.main.ObjectsStorage import objects_storage
from app.logging_config import getLogger
from app.database import session_scope, row2dict
from app.core.models.Clasess import Class, Object, Property, Value, Method, History
from app.core.main.ObjectManager import ObjectManager, PropertyManager, ObjectLoggerAdapter
from app.core.lib.constants import PropertyType

_logger = getLogger('object')
_UNSET = object()


def _get_object_logger(object_name: str):
    """Create a logger adapter with object name context"""
    return ObjectLoggerAdapter(_logger, {'object_name': object_name})

def addClass(name:str, description:str=_UNSET, parentId:int=_UNSET, update:bool=False) -> dict:
    """Add a class to the database.

    Args:
        name (str): Name class
        description (str, optional): Description class. Defaults to ''.
        parentId (int, optional): ID parent class. Defaults to None.
        update (bool, optional): Update existing class if it exists. Defaults to False.

    Returns:
        dict: Class row in DB
    """
    with session_scope() as session:
        cls = session.query(Class).filter(Class.name == name).one_or_none()
        if not cls:
            cls = Class()
            cls.name = name
            if description is not _UNSET:
                cls.description = description
            if parentId is not _UNSET:
                cls.parent_id = parentId
            session.add(cls)
            session.commit()
            objects_storage.reload_objects_by_class(cls.id)
        elif update:
            if description is not _UNSET:
                cls.description = description
            if parentId is not _UNSET:
                cls.parent_id = parentId
            session.commit()
            objects_storage.reload_objects_by_class(cls.id)
        return row2dict(cls)

def getClass(name:str) -> dict:
    """Get class from the database.

    Args:
        name (str): Name class

    Returns:
        dict: Class row in DB
    """
    with session_scope() as session:
        cls = session.query(Class).filter(Class.name == name).one_or_none()
        if cls:
            return row2dict(cls)
        return None

def updateClass(cls:dict) -> bool:
    """Update class in the database.

    Args:
        cls (Class): Class

    Returns:
        bool: Result
    """
    with session_scope() as session:
        rec = session.query(Class).filter(Class.name == cls['name']).one_or_none()
        if not rec:
            return False
        rec.name = cls['name']
        rec.description = cls['description']
        rec.parent_id = cls['parent_id']
        rec.template = cls['template']
        session.commit
        objects_storage.reload_objects_by_class(rec.id)
        return True


def addClassProperty(
    name: str,
    class_name: str,
    description: str = _UNSET,
    history: int = _UNSET,
    type: PropertyType = _UNSET,
    method_name: str = _UNSET,
    params: dict = _UNSET,
    update: bool = False,
) -> Property:
    """Add a property class to the database

    Args:
        name (str): Name
        class_name (str): Class name
        description (str, optional): Description property. Defaults to ''.
        history (int, optional): Save history (days). Defaults to 0.
        type (PropertyType, optional): Type property. Defaults to PropertyType.Empty.
        method_name (str, optional): Call method on change value property. Defaults to None.
        params (dict, optional): Property params JSON (icon, color, validation and UI metadata). Defaults to None.
        update (bool, optional): Update existing property if it exists. Defaults to False.

    Returns:
        Property: Property row in DB
    """
    with session_scope() as session:
        cls = session.query(Class).filter(Class.name == class_name).one_or_none()
        if not cls:
            return None
        prop = session.query(Property).filter(Property.name == name, Property.class_id == cls.id).one_or_none()
        if not prop:
            prop = Property()
            prop.name = name
            if description is not _UNSET:
                prop.description = description
            prop.class_id = cls.id
            prop.history = 0 if history is _UNSET else history
            prop.type = (PropertyType.Empty if type is _UNSET else type).value
            if params is not _UNSET:
                prop.params = json.dumps(params)
            if method_name is not _UNSET and method_name:
                method = session.query(Method).filter(Method.name == method_name, Method.class_id == cls.id).one_or_none()
                if method:
                    prop.method_id = method.id
            session.add(prop)
            session.commit()
            objects_storage.reload_objects_by_class(cls.id)
        elif update:
            if description is not _UNSET:
                prop.description = description
            if history is not _UNSET:
                prop.history = history
            if type is not _UNSET:
                prop.type = type.value
            if params is not _UNSET:
                prop.params = json.dumps(params)
            if method_name is not _UNSET:
                if method_name:
                    method = session.query(Method).filter(Method.name == method_name, Method.class_id == cls.id).one_or_none()
                    if method:
                        prop.method_id = method.id
                    else:
                        prop.method_id = None
                else:
                    prop.method_id = None
            session.commit()
            objects_storage.reload_objects_by_class(cls.id)
        return prop

def addClassMethod(
    name:str,
    class_name:str,
    description:str=_UNSET,
    code:str=_UNSET,
    call_parent:int=_UNSET,
    params:dict=_UNSET,
    update:bool=False,
) -> Method:
    """Add a method class to the database

    Args:
        name (str): Name
        class_name (str): Class name
        description (str, optional): Description method. Defaults to ''.
        code (str, optional): Python code. Defaults to ''.
        call_parent (int, optional): Call parent. Defaults to 0.
        params (dict, optional): Display params JSON (icon, color, sort_order). Defaults to None.
        update (bool, optional): Update existing method if it exists. Defaults to False.

    Returns:
        Method: Method row in DB
    """
    with session_scope() as session:
        cls = session.query(Class).filter(Class.name == class_name).one_or_none()
        if not cls:
            return None
        method = session.query(Method).filter(Method.name == name, Method.class_id == cls.id).one_or_none()
        if not method:
            method = Method()
            method.name = name
            method.class_id = cls.id
            if description is not _UNSET:
                method.description = description
            if code is not _UNSET:
                method.code = code
            method.call_parent = 0 if call_parent is _UNSET else call_parent
            if params is not _UNSET:
                method.params = json.dumps(params)
            session.add(method)
            session.commit()
            objects_storage.reload_objects_by_class(cls.id)
        elif update:
            if description is not _UNSET:
                method.description = description
            if code is not _UNSET:
                method.code = code
            if call_parent is not _UNSET:
                method.call_parent = call_parent
            if params is not _UNSET:
                method.params = json.dumps(params)
            session.commit()
            objects_storage.reload_objects_by_class(cls.id)
        return method

def addObject(name:str, class_name:str=_UNSET, description=_UNSET, update:bool=False) -> ObjectManager:
    """Add a object to the database

    Args:
        name (str): Name
        class_name (str): Class name
        description (str, optional): Description. Defaults to ''.
        update (bool, optional): Update existing object if it exists. Defaults to False.

    Returns:
        ObjectManager: Object
    """
    with session_scope() as session:
        obj = session.query(Object).filter(Object.name == name).one_or_none()
        if not obj:
            cls = None
            if class_name is not _UNSET and class_name:
                cls = session.query(Class).filter(Class.name == class_name).one_or_none()
            obj = Object()
            obj.name = name
            obj.class_id = cls.id if cls else None
            if description is not _UNSET:
                obj.description = description
            session.add(obj)
            session.commit()
            objects_storage.reload_object(obj.id)
        elif update:
            if class_name is not _UNSET:
                cls = session.query(Class).filter(Class.name == class_name).one_or_none()
                obj.class_id = cls.id if cls else obj.class_id
            if description is not _UNSET:
                obj.description = description
            session.commit()
            objects_storage.reload_object(obj.id)
        return objects_storage.getObjectByName(name)

def addObjectProperty(
    name:str,
    object_name:str,
    description:str=_UNSET,
    history:int=_UNSET,
    type:PropertyType=_UNSET,
    method_name:str=_UNSET,
    params:dict=_UNSET,
    update:bool=False,
) -> bool:
    """Add a property object to the database

    Args:
        name (str): Name
        object_name (str): Object name
        description (str, optional): Description. Defaults to ''.
        history (int, optional): Save history (days). Defaults to 0.
        type (PropertyType, optional): Type property. Defaults to PropertyType.Empty.
        method_name (str, optional): Call method on change value property. Defaults to None.
        params (dict, optional): Parameters property. Defaults to None.
        update (bool, optional): Update existing property if it exists. Defaults to False.

    Returns:
        bool: Success add property
    """
    with session_scope() as session:
        obj = session.query(Object).filter(Object.name == object_name).one_or_none()
        if not obj:
            return False
        prop = session.query(Property).filter(Property.name == name, Property.object_id == obj.id).one_or_none()
        if not prop:
            prop = Property()
            prop.name = name
            if description is not _UNSET:
                prop.description = description
            prop.object_id = obj.id
            prop.history = 0 if history is _UNSET else history
            prop.type = (PropertyType.Empty if type is _UNSET else type).value
            if params is not _UNSET:
                prop.params = json.dumps(params)
            if method_name is not _UNSET and method_name:
                method = session.query(Method).filter(Method.name == method_name, Method.object_id == obj.id).one_or_none()
                if method:
                    prop.method_id = method.id
                else:
                    cls = session.query(Class).filter(Class.id == obj.class_id).one_or_none()
                    if cls:
                        method = session.query(Method).filter(Method.name == method_name, Method.class_id == cls.id).one_or_none()
                        if method:
                            prop.method_id = method.id
            session.add(prop)
            session.commit()
            objects_storage.reload_object(obj.id)
        elif update:
            if description is not _UNSET:
                prop.description = description
            if history is not _UNSET:
                prop.history = history
            if type is not _UNSET:
                prop.type = type.value
            if params is not _UNSET:
                prop.params = json.dumps(params)
            if method_name is not _UNSET:
                if method_name:
                    method = session.query(Method).filter(Method.name == method_name, Method.object_id == obj.id).one_or_none()
                    if method:
                        prop.method_id = method.id
                    else:
                        cls = session.query(Class).filter(Class.id == obj.class_id).one_or_none()
                        if cls:
                            method = session.query(Method).filter(Method.name == method_name, Method.class_id == cls.id).one_or_none()
                            if method:
                                prop.method_id = method.id
                            else:
                                prop.method_id = None
                        else:
                            prop.method_id = None
                else:
                    prop.method_id = None
            session.commit()
            objects_storage.reload_object(obj.id)
        return True

def deleteObjectProperty(object_property: str) -> bool:
    """
    Delete a property object from the database using the format 'object_name.property_name'

    Args:
        object_property (str): String in the format 'object_name.property_name'

    Returns:
        bool: Success of deleting the property
    """
    try:
        object_name, property_name = object_property.split('.', 1)
    except ValueError:
        return False

    with session_scope() as session:
        obj = session.query(Object).filter(Object.name == object_name).one_or_none()
        if not obj:
            return False
        prop = session.query(Property).filter(Property.name == property_name, Property.object_id == obj.id).one_or_none()
        if not prop:
            return False
        values = session.query(Value).filter(Value.object_id == obj.id, Value.name == property_name).all()
        for value in values:
            session.query(History).filter(History.value_id == value.id).delete(synchronize_session=False)
            session.delete(value)
        session.delete(prop)
        session.commit()
        objects_storage.reload_object(obj.id)
        return True


def deleteClassProperty(class_property: str) -> bool:
    """
    Delete a class property from the database using the format 'class_name.property_name'

    Args:
        class_property (str): String in the format 'class_name.property_name'

    Returns:
        bool: Success of deleting the property
    """
    try:
        class_name, property_name = class_property.split('.', 1)
    except ValueError:
        return False

    with session_scope() as session:
        cls = session.query(Class).filter(Class.name == class_name).one_or_none()
        if not cls:
            return False
        prop = session.query(Property).filter(Property.name == property_name, Property.class_id == cls.id).one_or_none()
        if not prop:
            return False
        session.delete(prop)
        session.commit()
        objects_storage.reload_objects_by_class(cls.id)
        return True

def addObjectMethod(
    name:str,
    object_name:str,
    description:str=_UNSET,
    code:str=_UNSET,
    call_parent:int=_UNSET,
    params:dict=_UNSET,
    update:bool=False,
) -> bool:
    """Add a method object to the database

    Args:
        name (str): Name
        object_name (str): Name object
        description (str, optional): Description method. Defaults to ''.
        code (str, optional): Python code. Defaults to ''.
        call_parent (int, optional): Call parent. Defaults to 0.
        params (dict, optional): Display params JSON (icon, color, sort_order). Defaults to None.
        update (bool, optional): Update existing method if it exists. Defaults to False.

    Returns:
        bool: Success add method
    """
    with session_scope() as session:
        obj = session.query(Object).filter(Object.name == object_name).one_or_none()
        if not obj:
            return False
        obj_method = session.query(Method).filter(Method.name == name, Method.object_id == obj.id).one_or_none()
        class_method = None
        if not obj_method and obj.class_id:
            class_method = session.query(Method).filter(Method.name == name, Method.class_id == obj.class_id).one_or_none()
        if not obj_method and not class_method:
            # Method doesn't exist, create new object method
            method = Method()
            method.name = name
            method.object_id = obj.id
            if description is not _UNSET:
                method.description = description
            if code is not _UNSET:
                method.code = code
            method.call_parent = 0 if call_parent is _UNSET else call_parent
            if params is not _UNSET:
                method.params = json.dumps(params)
            session.add(method)
            session.commit()
            objects_storage.reload_object(obj.id)
        elif obj_method and update:
            # Object method exists, update it
            if description is not _UNSET:
                obj_method.description = description
            if code is not _UNSET:
                obj_method.code = code
            if call_parent is not _UNSET:
                obj_method.call_parent = call_parent
            if params is not _UNSET:
                obj_method.params = json.dumps(params)
            session.commit()
            objects_storage.reload_object(obj.id)
        elif not obj_method and class_method and update:
            # Only class method exists, create object method (override)
            method = Method()
            method.name = name
            method.object_id = obj.id
            if description is not _UNSET:
                method.description = description
            if code is not _UNSET:
                method.code = code
            method.call_parent = class_method.call_parent if call_parent is _UNSET else call_parent
            if params is not _UNSET:
                method.params = json.dumps(params)
            elif class_method.params:
                method.params = class_method.params
            session.add(method)
            session.commit()
            objects_storage.reload_object(obj.id)
        return True

def deleteObjectMethod(object_method: str) -> bool:
    """
    Delete a method object from the database using the format 'object_name.method_name'

    Args:
        object_method (str): String in the format 'object_name.method_name'

    Returns:
        bool: Success of deleting the method
    """
    try:
        object_name, method_name = object_method.split('.', 1)
    except ValueError:
        return False
    with session_scope() as session:
        obj = session.query(Object).filter(Object.name == object_name).one_or_none()
        if not obj:
            return False  # Объект не найден
        method = session.query(Method).filter(Method.name == method_name, Method.object_id == obj.id).one_or_none()
        if not method:
            return False
        session.delete(method)
        session.commit()
        objects_storage.reload_object(obj.id)
        return True


def deleteClassMethod(class_method: str) -> bool:
    """
    Delete a class method from the database using the format 'class_name.method_name'

    Args:
        class_method (str): String in the format 'class_name.method_name'

    Returns:
        bool: Success of deleting the method
    """
    try:
        class_name, method_name = class_method.split('.', 1)
    except ValueError:
        return False
    with session_scope() as session:
        cls = session.query(Class).filter(Class.name == class_name).one_or_none()
        if not cls:
            return False
        method = session.query(Method).filter(Method.name == method_name, Method.class_id == cls.id).one_or_none()
        if not method:
            return False
        session.delete(method)
        session.commit()
        objects_storage.reload_objects_by_class(cls.id)
        return True

def getObject(name:str) -> ObjectManager:
    """Get an object by its name

    Args:
        name (str): Name object

    Returns:
        ObjectManager: Object
    """
    logger = _get_object_logger(name)
    try:
        obj = objects_storage.getObjectByName(name)
        return obj
    except Exception as e:
        logger.exception('getObject %s: %s',name,e)
        return None

def getObjectsByClass(class_name:str, subclasses:bool=True) -> list[ObjectManager]:
    """get list object by class

    Args:
        class_name (str): Class name
        subclasses (bool, optional): Subclasses. Defaults to True.

    Returns:
        list[ObjectManager]: List objects
    """
    try:
        objects = []
        with session_scope() as session:
            cls = session.query(Class).filter(Class.name == class_name).one_or_none()
            if cls:
                objs = session.query(Object).filter(Object.class_id == cls.id).all()
                for obj in objs:
                    res = getObject(obj.name)
                    if res:
                        objects.append(res)
                if subclasses:
                    res = session.query(Class).filter(Class.parent_id == cls.id).all()
                    for subclass in res:
                        childs = getObjectsByClass(subclass.name,subclasses)
                        if childs:
                            objects += childs
                return objects
            else:
                return None
    except Exception as e:
        _logger.exception('getObjectsByClass %s: %s',class_name,e)
    return None

def getProperty(name:str, data:str = 'value'):
    """Get value property by its name.

    Args:
        name (str): Name property. Syntax: Object.Property
        data (str): Name data from property (value, changed, source). Default = value

    Returns:
        Any Value property
    """
    object_name = name.split(".")[0] if '.' in name else name
    logger = _get_object_logger(object_name)
    try:
        if not isinstance(name, str) or '.' not in name:
            logger.error('Invalid property name format: %s', name)
            return False
        obj = name.split(".")[0]
        prop = name.split(".")[1]
        obj = objects_storage.getObjectByName(obj)
        if obj:
            return obj.getProperty(prop, data)
        else:
            logger.error('Object %s not found', name)
            return None
    except Exception as e:
        logger.exception('getProperty %s: %s',name,e)
    return None

def setProperty(name:str, value, source:str='', save_history:bool=None, changed:datetime.datetime=None, track_stats:bool=True) -> bool:
    """Set value property by its name.

    Args:
        name (str): Name property. Syntax: Object.Property
        value (Any): Value
        source (str, optional): Source changing value. Defaults to ''.
        save_history (bool, optional): Save history of changing value. Defaults to None.
        changed (datetime.datetime, optional): Date/time for the value. Used when saving history. Defaults to None (current time).
        track_stats (bool, optional): Increment count_write/count_read counters. Defaults to True.

    Returns:
        bool: Success set value
    """
    object_name = name.split(".")[0] if '.' in name else name
    logger = _get_object_logger(object_name)
    try:
        logger.debug('setProperty %s %s %s', name, value, source)
        if not isinstance(name, str) or '.' not in name:
            logger.error('Invalid property name format: %s', name)
            return False
        obj = name.split(".")[0]
        prop = name.split(".")[1]
        obj = objects_storage.getObjectByName(obj)
        if obj:
            obj.setProperty(prop, value, source, save_history, changed, track_stats=track_stats)
            return True
        else:
            logger.error('Object %s not found', name)
            return False
    except PermissionError:
        raise
    except Exception as e:
        logger.exception('setProperty %s: %s',name,e)
    return False

def setPropertyThread(name:str, value, source:str='', save_history:bool=None):
    """Set value property by its name in thread.

    Args:
        name (str): Name property. Syntax: Object.Property
        value (Any): Value
        source (str, optional): Source changing value. Defaults to ''.
        save_history (bool, optional): Save history of changing value. Defaults to None.

    Returns:
        bool: Success set value
    """
    object_name = name.split(".")[0] if '.' in name else name
    logger = _get_object_logger(object_name)
    try:
        logger.debug('setProperty %s %s %s', name, value, source)
        if not isinstance(name, str) or '.' not in name:
            logger.error('Invalid property name format: %s', name)
            return False
        obj = name.split(".")[0]
        prop = name.split(".")[1]
        obj = objects_storage.getObjectByName(obj)
        if obj:

            def wrapper():
                obj.setProperty(prop, value, source, save_history)

            thread = threading.Thread(name="Thread_setProperty_" + name, target=wrapper)
            thread.start()
            return True
        else:
            logger.error('Object %s not found', name)
            return False
    except Exception as e:
        logger.exception('setPropertyThread %s: %s',name,e)
    return False

def setPropertyTimeout(name: str, value, timeout: int, source:str=""):
    """Set property on timeout

    Args:
        name (str): Name property. Syntax: Object.Property
        value (Any): Value
        timeout (int): Timeout seconds
        source (str, optional): Source changing value. Defaults to ''.
    """
    object_name = name.split(".")[0] if '.' in name else name
    logger = _get_object_logger(object_name)
    try:
        logger.debug('setPropertyTimeout %s %s timeout:%s %s', name, value, timeout, source)
        if not isinstance(name, str) or '.' not in name:
            logger.error('Invalid property name format: %s', name)
            return False
        obj = name.split(".")[0]
        prop = name.split(".")[1]
        obj = objects_storage.getObjectByName(obj)
        if obj:
            obj.setPropertyTimeout(prop, value, timeout, source)
            return True
        else:
            logger.error('Object %s not found', name)
            return False
    except Exception as e:
        logger.exception('setPropertyTimeout %s: %s',name,e)
    return False

def updateProperty(name:str, value, source:str='', track_stats:bool=True) -> bool:
    """Update property by its name if value changed.

    Args:
        name (str): Name property. Syntax: Object.Property
        value (Any): Value
        source (str, optional): Source changing value. Defaults to ''.
        track_stats (bool, optional): Increment count_write/count_read counters. Defaults to True.

    Returns:
        bool: Success set value
    """
    object_name = name.split(".")[0] if '.' in name else name
    logger = _get_object_logger(object_name)
    try:
        logger.debug('updateProperty %s %s %s', name, value, source)
        if not isinstance(name, str) or '.' not in name:
            logger.error('Invalid property name format: %s', name)
            return False
        obj = name.split(".")[0]
        prop = name.split(".")[1]
        obj = objects_storage.getObjectByName(obj)
        if obj:
            return obj.updateProperty(prop, value, source, track_stats=track_stats)
        else:
            logger.error('Object %s not found', name)
            return False
    except Exception as e:
        logger.exception('updateProperty %s: %s',name,e)
    return False

def updatePropertyThread(name:str, value, source:str='') -> bool:
    """Update property by its name if value changed in thread.

    Args:
        name (str): Name property. Syntax: Object.Property
        value (Any): Value
        source (str, optional): Source changing value. Defaults to ''.

    Returns:
        bool: Success set value
    """
    object_name = name.split(".")[0] if '.' in name else name
    logger = _get_object_logger(object_name)
    try:
        logger.debug('updatePropertyThread %s %s %s', name, value, source)
        if not isinstance(name, str) or '.' not in name:
            logger.error('Invalid property name format: %s', name)
            return False
        obj = name.split(".")[0]
        prop = name.split(".")[1]
        obj = objects_storage.getObjectByName(obj)
        if obj:

            def wrapper():
                obj.updateProperty(prop, value, source)

            thread = threading.Thread(name="Thread_updateProperty_" + name, target=wrapper)
            thread.start()
            return True
        else:
            logger.error('Object %s not found', name)
            return False
    except Exception as e:
        logger.exception('updateProperty %s: %s',name,e)
    return False

def updatePropertyTimeout(name:str, value, timeout:int, source:str='') -> bool:
    """Update property by its name if value changed on timeout.

    Args:
        name (str): Name property. Syntax: Object.Property
        value (Any): Value
        timeout (int): Timeout seconds
        source (str, optional): Source changing value. Defaults to ''.

    Returns:
        bool: Success set value
    """
    object_name = name.split(".")[0] if '.' in name else name
    logger = _get_object_logger(object_name)
    try:
        logger.debug('updatePropertyTimeout %s %s timeout:%s %s', name, value, timeout, source)
        if not isinstance(name, str) or '.' not in name:
            logger.error('Invalid property name format: %s', name)
            return False
        obj = name.split(".")[0]
        prop = name.split(".")[1]
        obj = objects_storage.getObjectByName(obj)
        if obj:
            obj.updatePropertyTimeout(prop, value, timeout, source)
        else:
            logger.error('Object %s not found', name)
        return True
    except Exception as e:
        logger.exception('updatePropertyTimeout %s: %s',name,e)
    return False

def callMethod(name:str, args={}, source:str='') -> str:
    """Call method by its name

    Args:
        name (str): Name method. Syntax: Object.Method
        args (dict, optional): Args. Defaults to {}.
        source (str, optional): Source changing value. Defaults to ''.
    """
    object_name = name.split(".")[0] if '.' in name else name
    logger = _get_object_logger(object_name)
    try:
        logger.debug('callMethod %s', name)
        if not isinstance(name, str) or '.' not in name:
            logger.error('Invalid method name format: %s', name)
            return False
        obj = name.split(".")[0]
        method = name.split(".")[1]
        obj = objects_storage.getObjectByName(obj)
        if obj:
            return obj.callMethod(method, args, source)
        else:
            logger.error('Object %s not found', name)
            return None
    except Exception as e:
        logger.exception('CallMethod %s: %s',name,e)
        return str(e)

def callMethodThread(name: str, args={}, source:str=''):
    """Call method by its name in thread

    Args:
        name (str): Name method. Syntax: Object.Method
        args (dict, optional): Args. Defaults to {}.
        source (str, optional): Source changing value. Defaults to ''.
    """
    object_name = name.split(".")[0] if '.' in name else name
    logger = _get_object_logger(object_name)
    try:
        logger.debug('callMethodThread %s source:%s', name, source)
        if not isinstance(name, str) or '.' not in name:
            logger.error('Invalid method name format: %s', name)
            return False
        object_name = name.split(".")[0]
        method = name.split(".")[1]
        obj = objects_storage.getObjectByName(object_name)
        if obj:

            def wrapper():
                obj.callMethod(method, args, source)

            thread = threading.Thread(name="Thread_callMethod_" + name, target=wrapper)
            thread.start()
        else:
            logger.error('Object %s not found', name)
    except Exception as e:
        logger.exception('CallMethodThread %s: %s',name,e)

def callMethodTimeout(name:str, timeout:int, source:str=''):
    """Call method by its name

    Args:
        name (str): Name method. Syntax: Object.Method
        timeout (int): Timeout seconds
        source (str, optional): Source changing value. Defaults to ''.
    """
    object_name = name.split(".")[0] if '.' in name else name
    logger = _get_object_logger(object_name)
    try:
        logger.debug('callMethodTimeout %s timeout:%s source:%s', name, timeout, source)
        if not isinstance(name, str) or '.' not in name:
            logger.error('Invalid method name format: %s', name)
            return False
        obj = name.split(".")[0]
        method = name.split(".")[1]
        obj = objects_storage.getObjectByName(obj)
        if obj:
            obj.callMethodTimeout(method, timeout, source)
        else:
            logger.error('Object %s not found', name)
    except Exception as e:
        logger.exception('callMethodTimeout %s: %s',name,e)

def deleteObject(name: str):
    """Delete object from database

    Args:
        name (str): Name object
    """
    from app.database import db
    from app.core.lib.object_db import delete_object_from_db

    obj = Object.query.filter(Object.name == name).one_or_none()
    if not obj:
        return False
    deleted_name = delete_object_from_db(obj.id)
    db.session.commit()
    if deleted_name:
        objects_storage.remove_object(deleted_name)
        return True
    return False

def renameObject(old_name: str, new_name: str) -> bool:
    """Rename object in the database.

    Args:
        old_name (str): Current object name
        new_name (str): New object name

    Returns:
        bool: Success rename

    Raises:
        PermissionError: If the new name is already taken
    """
    old_name = (old_name or "").strip()
    new_name = (new_name or "").strip()
    if not old_name or not new_name or old_name == new_name:
        return False

    logger = _get_object_logger(old_name)
    with session_scope() as session:
        obj = session.query(Object).filter(Object.name == old_name).one_or_none()
        if not obj:
            logger.error('Object %s not found for rename', old_name)
            return False
        if session.query(Object).filter(Object.name == new_name).one_or_none():
            raise PermissionError(f'Object "{new_name}" already exists')
        obj.name = new_name
        session.commit()
        object_id = obj.id

    perm_key_old = f"object:{old_name}"
    perm_key_new = f"object:{new_name}"
    perm_value = getProperty(f"_permissions.{perm_key_old}")
    if perm_value is not None:
        setProperty(f"_permissions.{perm_key_new}", perm_value, "renameObject")
        deleteObjectProperty(f"_permissions.{perm_key_old}")

    objects_storage.rename_object(old_name, new_name, object_id)
    return True

def setLinkToObject(object_name:str, property_name:str, link:str) -> bool:
    """Set link for value

    Args:
        object_name (str): Name object
        property_name (str): Name property
        link (str): Name module

    Returns:
        bool: Success set link
    """
    obj = objects_storage.getObjectByName(object_name)
    if obj:
        if property_name in obj.properties:
            prop: PropertyManager = obj.properties[property_name]
            if not prop.linked:
                prop.linked = []
            if link not in prop.linked:
                prop.linked.append(link)
                id = prop.value_id
                with session_scope() as session:
                    rec = session.query(Value).where(Value.id == id).one_or_none()
                    if rec:
                        rec.linked = ','.join(prop.linked)
                        session.commit()
                return True
            else:
                return True
    return False

def removeLinkFromObject(object_name:str, property_name:str, link:str) -> bool:
    """Remove link from value

    Args:
        object_name (str): Name object
        property_name (str): Name property
        link (str): Name module

    Returns:
        bool: Success set link
    """
    obj = objects_storage.getObjectByName(object_name)
    if obj:
        if property_name in obj.properties:
            prop: PropertyManager = obj.properties[property_name]
            if prop.linked and link in prop.linked:
                prop.linked.remove(link)
                id = prop.value_id
                with session_scope() as session:
                    rec = session.query(Value).where(Value.id == id).one_or_none()
                    if rec:
                        rec.linked = ','.join(prop.linked)
                        session.commit()
                return True
            else:
                return True
    return False

def clearLinkedObjects(link:str):
    """Clear link in all objects

    Args:
        link (str): Name module
    """
    with session_scope() as session:
        for obj in objects_storage.values():
            for _, prop in obj.properties:
                if prop.linked and link in prop.linked:
                    prop.linked.remove(link)
                    id = prop._value_id
                    rec = session.query(Value).where(Value.id == id).one_or_none()
                    if rec:
                        rec.linked = ','.join(prop.linked)

        session.commit()


def getHistory(name:str, dt_begin:datetime = None, dt_end:datetime = None, limit:int = None, order_desc: bool = False, func=None) -> list:
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
    object_name = name.split(".")[0] if '.' in name else name
    logger = _get_object_logger(object_name)
    try:
        logger.debug('getHistory %s', name)
        if not isinstance(name, str) or '.' not in name:
            logger.error('Invalid property name format: %s', name)
            return None
        obj = name.split(".")[0]
        prop = name.split(".")[1]
        obj = objects_storage.getObjectByName(obj)
        if obj:
            return obj.getHistory(prop, dt_begin, dt_end, limit, order_desc, func)
        else:
            logger.error('Object %s not found', name)
            return None
    except Exception as e:
        logger.exception('getHistory %s: %s',name,e)
    return None

def getHistoryAggregate(name:str, dt_begin:datetime = None, dt_end:datetime = None, func:str = None):
    """Get aggregate history of a property

    Args:
        name (str): Name property
        dt_begin (datetime, optional): Begin local datetime. Defaults to None.
        dt_end (datetime, optional): End local datetime. Defaults to None.
        func (str, optional): Aggregate function (min,max,sum,avg,count). Defaults to None, return all

    Returns:
        any : Result function
    """
    object_name = name.split(".")[0] if '.' in name else name
    logger = _get_object_logger(object_name)
    try:
        logger.debug('getHistoryAggregate %s', name)
        if not isinstance(name, str) or '.' not in name:
            logger.error('Invalid property name format: %s', name)
            return None
        obj = name.split(".")[0]
        prop = name.split(".")[1]
        obj = objects_storage.getObjectByName(obj)
        if obj:
            return obj.getHistoryAggregate(prop, dt_begin, dt_end, func)
        else:
            logger.error('Object %s not found', name)
            return None
    except Exception as e:
        logger.exception('getHistoryAggregate %s: %s',name,e)
    return None


def addCustomFunction(
    name: str,
    code: str = _UNSET,
    test_code: str = _UNSET,
    description: str = _UNSET,
    order: int = _UNSET,
    active: bool = _UNSET,
    update: bool = False,
) -> bool:
    """Add or update a CustomFunction in the database."""
    from app.core.models.CustomFunctions import CustomFunction
    from app.core.main.CustomFunctionRegistry import custom_function_registry

    with session_scope() as session:
        row = session.query(CustomFunction).filter(CustomFunction.name == name).one_or_none()
        if not row:
            row = CustomFunction()
            row.name = name
            row.code = '' if code is _UNSET else code
            row.test_code = '' if test_code is _UNSET else test_code
            row.description = '' if description is _UNSET else description
            row.order = 0 if order is _UNSET else order
            row.active = True if active is _UNSET else active
            session.add(row)
            session.commit()
        elif not update:
            return False
        else:
            if code is not _UNSET:
                row.code = code
            if test_code is not _UNSET:
                row.test_code = test_code
            if description is not _UNSET:
                row.description = description
            if order is not _UNSET:
                row.order = order
            if active is not _UNSET:
                row.active = active
            session.commit()

    custom_function_registry.reload(name)
    return True


def deleteCustomFunction(name: str) -> bool:
    from app.core.models.CustomFunctions import CustomFunction
    from app.core.main.CustomFunctionRegistry import custom_function_registry

    with session_scope() as session:
        row = session.query(CustomFunction).filter(CustomFunction.name == name).one_or_none()
        if not row:
            return False
        session.delete(row)
        session.commit()
    custom_function_registry.reload(name)
    return True


def listCustomFunctions() -> list:
    from app.core.models.CustomFunctions import CustomFunction
    from app.core.main.CustomFunctionRegistry import custom_function_registry

    errors = custom_function_registry.get_compile_errors()
    with session_scope() as session:
        rows = session.query(CustomFunction).order_by(CustomFunction.order, CustomFunction.name).all()
        return [
            {
                'name': r.name,
                'description': r.description,
                'active': r.active,
                'order': r.order,
                'has_error': r.name in errors,
                'error': errors.get(r.name),
            }
            for r in rows
        ]


def runCustomFunctionTest(name: str, test_code: str = None, params=None) -> tuple:
    """Run test_code for CustomFunction. Returns (output, success)."""
    from app.core.models.CustomFunctions import CustomFunction
    from app.core.lib.execute import execute_and_capture_output

    with session_scope() as session:
        row = session.query(CustomFunction).filter(CustomFunction.name == name).one_or_none()
        if not row:
            return 'CustomFunction not found.', False
        code = test_code if test_code is not None else (row.test_code or '')

    if not code.strip():
        return 'test_code is empty.', False

    variables = {'params': params, 'logger': _logger}
    output, error = execute_and_capture_output(
        code,
        variables,
        code_filename=f'<Test:{name}>',
        method_context={'source': f'CustomFunction.test:{name}'},
    )
    return output, not error
