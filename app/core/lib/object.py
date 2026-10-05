"""Object / class API for osysHome (CRUD, properties, methods, links, history)."""
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
from app.core.lib.object_tree import invalidate_objects_tree_cache

_logger = getLogger('object')
_UNSET = object()


def _get_object_logger(object_name: str):
    """Return a logger adapter bound to an object name.

    Args:
        object_name (str): Object name for log context.

    Returns:
        ObjectLoggerAdapter: Logger with ``object_name`` in extra context.
    """
    return ObjectLoggerAdapter(_logger, {'object_name': object_name})

def addClass(name:str, description:str=_UNSET, parentId:int=_UNSET, update:bool=False) -> dict:
    """Create or update a class in the database.

    Args:
        name (str): Class name.
        description (str, optional): Class description. Omitted fields are not
            set on create. Defaults to sentinel (unchanged / not set).
        parentId (int, optional): Parent class ID. Defaults to sentinel.
        update (bool, optional): If True, update an existing class with the
            same name. Defaults to False.

    Returns:
        dict: Class row as a dict (via ``row2dict``).
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
            invalidate_objects_tree_cache()
        elif update:
            if description is not _UNSET:
                cls.description = description
            if parentId is not _UNSET:
                cls.parent_id = parentId
            session.commit()
            objects_storage.reload_objects_by_class(cls.id)
            invalidate_objects_tree_cache()
        return row2dict(cls)

def getClass(name:str) -> dict:
    """Get a class by name from the database.

    Args:
        name (str): Class name.

    Returns:
        dict: Class row as a dict.
            None if the class does not exist.
    """
    with session_scope() as session:
        cls = session.query(Class).filter(Class.name == name).one_or_none()
        if cls:
            return row2dict(cls)
        return None

def updateClass(cls:dict) -> bool:
    """Update an existing class in the database.

    Args:
        cls (dict): Class fields: ``name``, ``description``, ``parent_id``,
            ``template``.

    Returns:
        bool: True if the class was found and updated, False otherwise.
    """
    with session_scope() as session:
        rec = session.query(Class).filter(Class.name == cls['name']).one_or_none()
        if not rec:
            return False
        rec.name = cls['name']
        rec.description = cls['description']
        rec.parent_id = cls['parent_id']
        rec.template = cls['template']
        session.commit()
        objects_storage.reload_objects_by_class(rec.id)
        invalidate_objects_tree_cache()
        return True

def listClasses() -> list[dict]:
    """List all classes from the database.

    Returns:
        list[dict]: Class rows ordered by name.
            On error returns None.
    """
    try:
        with session_scope() as session:
            classes = session.query(Class).order_by(Class.name).all()
            return [row2dict(cls) for cls in classes]
    except Exception as e:
        _logger.exception('listClasses: %s', e)
    return None

def getChildClasses(name:str, recursive:bool=False) -> list[dict]:
    """Get child classes of the given class.

    Args:
        name (str): Parent class name
        recursive (bool, optional): If True, include all descendants
            (depth-first). If False, only direct children. Defaults to False.

    Returns:
        list[dict]: Child class rows ordered by name at each level.
            Empty list if the class has no children.
            None if the class does not exist or on error.
    """
    try:
        result = []
        with session_scope() as session:
            cls = session.query(Class).filter(Class.name == name).one_or_none()
            if not cls:
                return None

            def _add_children(parent_id: int):
                children = session.query(Class).filter(Class.parent_id == parent_id).order_by(Class.name).all()
                for child in children:
                    result.append(row2dict(child))
                    if recursive:
                        _add_children(child.id)

            _add_children(cls.id)
        return result
    except Exception as e:
        _logger.exception('getChildClasses %s: %s', name, e)
    return None

def getClassParents(name:str) -> list[dict]:
    """Get the parent chain of a class (does not include the class itself).

    Args:
        name (str): Class name

    Returns:
        list[dict]: Parent class rows from immediate parent up to root.
            Empty list if the class has no parent.
            None if the class does not exist or on error.
    """
    try:
        result = []
        with session_scope() as session:
            cls = session.query(Class).filter(Class.name == name).one_or_none()
            if not cls:
                return None
            parent_id = cls.parent_id
            while parent_id:
                parent = session.query(Class).filter(Class.id == parent_id).one_or_none()
                if not parent:
                    break
                result.append(row2dict(parent))
                parent_id = parent.parent_id
        return result
    except Exception as e:
        _logger.exception('getClassParents %s: %s', name, e)
    return None

def deleteClass(name:str) -> bool:
    """Delete a class from the database.

    Refuses deletion (returns False) if:
      - the class does not exist;
      - the class has child classes;
      - the class has any objects.

    On success also deletes class-level properties and methods
    and invalidates the objects tree cache.

    Args:
        name (str): Class name

    Returns:
        bool: True if deleted, False otherwise
    """
    try:
        with session_scope() as session:
            cls = session.query(Class).filter(Class.name == name).one_or_none()
            if not cls:
                return False
            if session.query(Class.id).filter(Class.parent_id == cls.id).first():
                return False
            if session.query(Object.id).filter(Object.class_id == cls.id).first():
                return False
            session.query(Property).filter(Property.class_id == cls.id).delete(synchronize_session=False)
            session.query(Method).filter(Method.class_id == cls.id).delete(synchronize_session=False)
            session.delete(cls)
            session.commit()
        invalidate_objects_tree_cache()
        return True
    except Exception as e:
        _logger.exception('deleteClass %s: %s', name, e)
    return False


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
    """Create or update a class-level property in the database.

    Args:
        name (str): Property name.
        class_name (str): Class name.
        description (str, optional): Property description. Omitted fields use
            defaults on create. Defaults to sentinel.
        history (int, optional): History retention in days. Defaults to 0 when
            omitted on create.
        type (PropertyType, optional): Property type. Defaults to
            ``PropertyType.Empty`` when omitted on create.
        method_name (str, optional): Method to call when the value changes.
            Defaults to sentinel.
        params (dict, optional): Property params JSON (icon, color, validation,
            UI metadata). Defaults to sentinel.
        update (bool, optional): If True, update an existing property.
            Defaults to False.

    Returns:
        Property: Property ORM instance.
            None if the class does not exist.
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
    """Create or update a class-level method in the database.

    Args:
        name (str): Method name.
        class_name (str): Class name.
        description (str, optional): Method description. Defaults to sentinel.
        code (str, optional): Python method body. Defaults to sentinel.
        call_parent (int, optional): Whether to invoke the parent method.
            Defaults to 0 when omitted on create.
        params (dict, optional): Display params JSON (icon, color, sort_order).
            Defaults to sentinel.
        update (bool, optional): If True, update an existing method.
            Defaults to False.

    Returns:
        Method: Method ORM instance.
            None if the class does not exist.
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
    """Create or update an object in the database.

    Loads or reloads the object in ``objects_storage`` and returns its
    ``ObjectManager``.

    Args:
        name (str): Object name.
        class_name (str, optional): Class name. Defaults to sentinel.
        description (str, optional): Object description. Defaults to sentinel.
        update (bool, optional): If True, update an existing object.
            Defaults to False.

    Returns:
        ObjectManager: Runtime object wrapper from ``objects_storage``.
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
            invalidate_objects_tree_cache()
        elif update:
            if class_name is not _UNSET:
                cls = session.query(Class).filter(Class.name == class_name).one_or_none()
                obj.class_id = cls.id if cls else obj.class_id
            if description is not _UNSET:
                obj.description = description
            session.commit()
            objects_storage.reload_object(obj.id)
            invalidate_objects_tree_cache()
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
    """Create or update an object-level property in the database.

    Args:
        name (str): Property name.
        object_name (str): Object name.
        description (str, optional): Property description. Defaults to sentinel.
        history (int, optional): History retention in days. Defaults to 0 when
            omitted on create.
        type (PropertyType, optional): Property type. Defaults to
            ``PropertyType.Empty`` when omitted on create.
        method_name (str, optional): Method to call on value change; resolves
            object method first, then class method. Defaults to sentinel.
        params (dict, optional): Property params JSON. Defaults to sentinel.
        update (bool, optional): If True, update an existing property.
            Defaults to False.

    Returns:
        bool: True on success, False if the object does not exist.
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
    """Delete an object-level property and its values/history.

    Args:
        object_property (str): Qualified name ``object_name.property_name``.

    Returns:
        bool: True if deleted, False if the name is invalid or the property
            does not exist.
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
        object_id = obj.id
    objects_storage.changeObject("delete", object_name, property_name, None, None)
    objects_storage.reload_object(object_id)
    return True


def deleteClassProperty(class_property: str) -> bool:
    """Delete a class-level property definition.

    Reloads all objects of that class and notifies ``objects_storage``.

    Args:
        class_property (str): Qualified name ``class_name.property_name``.

    Returns:
        bool: True if deleted, False if the name is invalid or the property
            does not exist.
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
        object_names = [
            name for (name,) in session.query(Object.name).filter(Object.class_id == cls.id).all()
        ]
        class_id = cls.id
        session.delete(prop)
        session.commit()
    for obj_name in object_names:
        objects_storage.changeObject("delete", obj_name, property_name, None, None)
    objects_storage.reload_objects_by_class(class_id)
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
    """Create or update an object-level method in the database.

    If only a class method exists and ``update`` is True, creates an object
    method that overrides the class definition.

    Args:
        name (str): Method name.
        object_name (str): Object name.
        description (str, optional): Method description. Defaults to sentinel.
        code (str, optional): Python method body. Defaults to sentinel.
        call_parent (int, optional): Whether to invoke the parent method.
            Defaults to sentinel (inherits from class method when overriding).
        params (dict, optional): Display params JSON. Defaults to sentinel.
        update (bool, optional): If True, update or override an existing method.
            Defaults to False.

    Returns:
        bool: True on success, False if the object does not exist.
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
    """Delete an object-level method.

    Args:
        object_method (str): Qualified name ``object_name.method_name``.

    Returns:
        bool: True if deleted, False if the name is invalid, the object is
            missing, or the method does not exist.
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
        object_id = obj.id
        session.delete(method)
        session.commit()
    objects_storage.changeObject("delete", object_name, None, method_name, None)
    objects_storage.reload_object(object_id)
    return True


def deleteClassMethod(class_method: str) -> bool:
    """Delete a class-level method definition.

    Reloads all objects of that class and notifies ``objects_storage``.

    Args:
        class_method (str): Qualified name ``class_name.method_name``.

    Returns:
        bool: True if deleted, False if the name is invalid or the method
            does not exist.
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
        object_names = [
            name for (name,) in session.query(Object.name).filter(Object.class_id == cls.id).all()
        ]
        class_id = cls.id
        session.delete(method)
        session.commit()
    for obj_name in object_names:
        objects_storage.changeObject("delete", obj_name, None, method_name, None)
    objects_storage.reload_objects_by_class(class_id)
    return True

def getObject(name:str) -> ObjectManager:
    """Get an object by name from the runtime cache.

    Args:
        name (str): Object name.

    Returns:
        ObjectManager: Runtime object wrapper.
            None if the object is missing or on error.
    """
    logger = _get_object_logger(name)
    try:
        obj = objects_storage.getObjectByName(name)
        return obj
    except Exception as e:
        logger.exception('getObject %s: %s',name,e)
        return None

def listObjects() -> list[ObjectManager]:
    """List all objects from the runtime cache.

    Enumeration via ``objects_storage`` syncs missing objects from DB first,
    so objects that were not loaded yet are included.

    Returns:
        list[ObjectManager]: All objects.
            On error returns None.
    """
    try:
        return list(objects_storage.values())
    except Exception as e:
        _logger.exception('listObjects: %s', e)
    return None

def objectExists(name:str) -> bool:
    """Check whether an object with the given name exists.

    If the object is already in the runtime cache, returns True without
    a DB query. Otherwise checks the database and does not create
    an ObjectManager.

    Args:
        name (str): Object name

    Returns:
        bool: True if the object exists, False otherwise
    """
    try:
        if name in objects_storage.objects:
            return True
        with session_scope() as session:
            return session.query(Object.id).filter(Object.name == name).first() is not None
    except Exception as e:
        _logger.exception('objectExists %s: %s', name, e)
    return False

def getObjectClass(name:str) -> dict:
    """Get the class row of an object.

    Resolves the object's own class (first entry in ``parents``),
    not parent classes in the inheritance chain.

    Args:
        name (str): Object name

    Returns:
        dict: Class row from DB.
            None if the object is missing, has no class, or on error.
    """
    try:
        obj = getObject(name)
        if not obj:
            return None
        parents = getattr(obj, 'parents', None) or []
        if not parents:
            return None
        return getClass(parents[0])
    except Exception as e:
        _logger.exception('getObjectClass %s: %s', name, e)
    return None

def getObjectsByClass(class_name:str, subclasses:bool=True) -> list[ObjectManager]:
    """List objects assigned to a class.

    Args:
        class_name (str): Class name.
        subclasses (bool, optional): If True, include objects of descendant
            classes. Defaults to True.

    Returns:
        list[ObjectManager]: Matching objects.
            None if the class does not exist or on error.
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

def getObjectsByProperty(property_name:str) -> list[ObjectManager]:
    """Get objects that have a property with the given name.

    Searches the runtime cache (``objects_storage``). Enumeration syncs
    missing objects from DB first. Inherited class properties are already
    resolved on each ObjectManager, so objects that only inherit the
    property are included.

    Args:
        property_name (str): Property name

    Returns:
        list[ObjectManager]: Matching objects.
            On error returns None.
    """
    try:
        return [
            obj for obj in objects_storage.values()
            if property_name in obj.properties
        ]
    except Exception as e:
        _logger.exception('getObjectsByProperty %s: %s', property_name, e)
    return None

def getObjectsByMethod(method_name:str) -> list[ObjectManager]:
    """Get objects that have a method with the given name.

    Searches the runtime cache (``objects_storage``). Enumeration syncs
    missing objects from DB first. Inherited class methods are already
    resolved on each ObjectManager, so objects that only inherit the
    method are included.

    Args:
        method_name (str): Method name

    Returns:
        list[ObjectManager]: Matching objects.
            On error returns None.
    """
    try:
        return [
            obj for obj in objects_storage.values()
            if method_name in obj.methods
        ]
    except Exception as e:
        _logger.exception('getObjectsByMethod %s: %s', method_name, e)
    return None

def getObjectsByPropertyValue(property_name:str, value) -> list[ObjectManager]:
    """Get objects whose property value equals ``value``.

    Searches the runtime cache (``objects_storage``). Enumeration syncs
    missing objects from DB first. Comparison uses decoded property values
    (``getValue(track_stats=False)``) and does not increment read stats.

    Args:
        property_name (str): Property name
        value (Any): Expected property value

    Returns:
        list[ObjectManager]: Matching objects.
            On error returns None.
    """
    try:
        result = []
        for obj in objects_storage.values():
            prop = obj.properties.get(property_name)
            if prop is None:
                continue
            if prop.getValue(track_stats=False) == value:
                result.append(obj)
        return result
    except Exception as e:
        _logger.exception('getObjectsByPropertyValue %s: %s', property_name, e)
    return None

def getClassesByProperty(property_name:str, subclasses:bool=True) -> list[dict]:
    """Get classes that define a property with the given name.

    Looks up class-level property definitions in the database.
    Object-level properties are not considered.

    Args:
        property_name (str): Property name
        subclasses (bool, optional): If True, also include subclasses of
            classes that define the property. Defaults to True.

    Returns:
        list[dict]: Matching class rows.
            On error returns None.
    """
    try:
        result = []
        seen = set()
        with session_scope() as session:
            classes = (
                session.query(Class)
                .join(Property, Property.class_id == Class.id)
                .filter(Property.name == property_name)
                .all()
            )

            def _add_class(cls, with_subclasses: bool):
                if cls.name not in seen:
                    result.append(row2dict(cls))
                    seen.add(cls.name)
                if with_subclasses:
                    children = session.query(Class).filter(Class.parent_id == cls.id).all()
                    for child in children:
                        _add_class(child, True)

            for cls in classes:
                _add_class(cls, subclasses)
        return result
    except Exception as e:
        _logger.exception('getClassesByProperty %s: %s', property_name, e)
    return None

def getClassesByMethod(method_name:str, subclasses:bool=True) -> list[dict]:
    """Get classes that define a method with the given name.

    Looks up class-level method definitions in the database.
    Object-level methods are not considered.

    Args:
        method_name (str): Method name
        subclasses (bool, optional): If True, also include subclasses of
            classes that define the method. Defaults to True.

    Returns:
        list[dict]: Matching class rows.
            On error returns None.
    """
    try:
        result = []
        seen = set()
        with session_scope() as session:
            classes = (
                session.query(Class)
                .join(Method, Method.class_id == Class.id)
                .filter(Method.name == method_name)
                .all()
            )

            def _add_class(cls, with_subclasses: bool):
                if cls.name not in seen:
                    result.append(row2dict(cls))
                    seen.add(cls.name)
                if with_subclasses:
                    children = session.query(Class).filter(Class.parent_id == cls.id).all()
                    for child in children:
                        _add_class(child, True)

            for cls in classes:
                _add_class(cls, subclasses)
        return result
    except Exception as e:
        _logger.exception('getClassesByMethod %s: %s', method_name, e)
    return None

def getProperty(name:str, data:str = 'value'):
    """Read a property field by qualified name.

    Args:
        name (str): Qualified name ``Object.Property``.
        data (str, optional): Field to read: ``value``, ``changed``, or
            ``source``. Defaults to ``value``.

    Returns:
        Any: Requested property field.
            False if ``name`` format is invalid.
            None if the object is missing or on error.
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
    """Set a property value by qualified name.

    Args:
        name (str): Qualified name ``Object.Property``.
        value (Any): New value.
        source (str, optional): Change source label. Defaults to ``''``.
        save_history (bool, optional): Override history persistence.
            Defaults to None (property default).
        changed (datetime.datetime, optional): Timestamp for history.
            Defaults to None (current time).
        track_stats (bool, optional): Increment read/write counters.
            Defaults to True.

    Returns:
        bool: True if the value was set, False on failure or invalid name.

    Raises:
        PermissionError: Propagated from ``ObjectManager.setProperty``.
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
            # Propagate ObjectManager result (False on reactive-loop block, etc.)
            return bool(
                obj.setProperty(
                    prop, value, source, save_history, changed, track_stats=track_stats
                )
            )
        else:
            logger.error('Object %s not found', name)
            return False
    except PermissionError:
        raise
    except Exception as e:
        logger.exception('setProperty %s: %s',name,e)
    return False

def setPropertyThread(name:str, value, source:str='', save_history:bool=None):
    """Set a property value asynchronously in a background thread.

    Args:
        name (str): Qualified name ``Object.Property``.
        value (Any): New value.
        source (str, optional): Change source label. Defaults to ``''``.
        save_history (bool, optional): Override history persistence.
            Defaults to None (property default).

    Returns:
        bool: True if the thread was started, False on failure or invalid name.
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
    """Schedule a property value change after a delay.

    Args:
        name (str): Qualified name ``Object.Property``.
        value (Any): Value to apply after the timeout.
        timeout (int): Delay in seconds.
        source (str, optional): Change source label. Defaults to ``''``.

    Returns:
        bool: True if the timeout was scheduled, False on failure or invalid
            name.
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
    """Set a property value only if it differs from the current value.

    Args:
        name (str): Qualified name ``Object.Property``.
        value (Any): New value.
        source (str, optional): Change source label. Defaults to ``''``.
        track_stats (bool, optional): Increment read/write counters.
            Defaults to True.

    Returns:
        bool: Result of ``ObjectManager.updateProperty``, or False on failure.
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
    """Conditionally update a property value in a background thread.

    Args:
        name (str): Qualified name ``Object.Property``.
        value (Any): New value.
        source (str, optional): Change source label. Defaults to ``''``.

    Returns:
        bool: True if the thread was started, False on failure or invalid name.
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
    """Schedule a conditional property update after a delay.

    Args:
        name (str): Qualified name ``Object.Property``.
        value (Any): Value to apply if still different after the timeout.
        timeout (int): Delay in seconds.
        source (str, optional): Change source label. Defaults to ``''``.

    Returns:
        bool: True when the call completes without exception (including when
            the object is missing). False on invalid name or on error.
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
    """Invoke an object method by qualified name.

    Args:
        name (str): Qualified name ``Object.Method``.
        args (dict, optional): Method arguments. Defaults to ``{}``.
        source (str, optional): Invocation source label. Defaults to ``''``.

    Returns:
        str: Method return value as a string.
            False if ``name`` format is invalid.
            None if the object is missing.
            Error message string on exception.
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
    """Invoke an object method asynchronously in a background thread.

    Args:
        name (str): Qualified name ``Object.Method``.
        args (dict, optional): Method arguments. Defaults to ``{}``.
        source (str, optional): Invocation source label. Defaults to ``''``.

    Returns:
        bool: False if ``name`` format is invalid; otherwise None.
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
    """Schedule a method invocation after a delay.

    Args:
        name (str): Qualified name ``Object.Method``.
        timeout (int): Delay in seconds.
        source (str, optional): Invocation source label. Defaults to ``''``.

    Returns:
        bool: False if ``name`` format is invalid; otherwise None.
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
    """Delete an object from the database and runtime cache.

    Args:
        name (str): Object name.

    Returns:
        bool: True if deleted, False if the object does not exist.
    """
    from app.database import db
    from app.core.lib.object_db import delete_object_from_db

    obj = Object.query.filter(Object.name == name).one_or_none()
    if not obj:
        return False
    deleted_name = delete_object_from_db(obj.id)
    db.session.commit()
    if deleted_name:
        objects_storage.changeObject("delete", deleted_name, None, None, None)
        objects_storage.remove_object(deleted_name)
        invalidate_objects_tree_cache()
        return True
    return False

def renameObject(old_name: str, new_name: str) -> bool:
    """Rename an object in the database and runtime cache.

    Migrates ``_permissions`` entries when present.

    Args:
        old_name (str): Current object name.
        new_name (str): New object name.

    Returns:
        bool: True if renamed, False if names are invalid or the object is
            missing.

    Raises:
        PermissionError: If ``new_name`` is already taken.
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
    invalidate_objects_tree_cache()
    return True

def setLinkToObject(object_name:str, property_name:str, link:str) -> bool:
    """Add a plugin/module link to a property's ``linked`` list.

    Persists the comma-separated link list on the ``Value`` row.

    Args:
        object_name (str): Object name.
        property_name (str): Property name on that object.
        link (str): Module or plugin link identifier.

    Returns:
        bool: True if the link was added or already present, False if the
            object or property is missing.
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
    """Remove a plugin/module link from a property's ``linked`` list.

    Args:
        object_name (str): Object name.
        property_name (str): Property name on that object.
        link (str): Module or plugin link identifier.

    Returns:
        bool: True if the link was removed or was not present, False if the
            object or property is missing.
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

def getObjectsByLink(link:str) -> list[ObjectManager]:
    """Get objects that have at least one property linked to a module.

    Searches the runtime cache (``objects_storage``). Enumeration syncs
    missing objects from DB first. A match is any property whose
    ``linked`` list contains ``link`` (see ``setLinkToObject``).

    Args:
        link (str): Module / plugin link name

    Returns:
        list[ObjectManager]: Matching objects (each object once).
            On error returns None.
    """
    try:
        result = []
        for obj in objects_storage.values():
            for prop in obj.properties.values():
                if prop.linked and link in prop.linked:
                    result.append(obj)
                    break
        return result
    except Exception as e:
        _logger.exception('getObjectsByLink %s: %s', link, e)
    return None

def clearLinkedObjects(link:str):
    """Remove a module link from all object properties.

    Updates both the runtime cache and the Value.linked field in DB.
    Opposite of ``setLinkToObject`` / pair to ``getObjectsByLink``.

    Args:
        link (str): Module / plugin link name.

    Returns:
        None
    """
    with session_scope() as session:
        for obj in objects_storage.values():
            for prop in obj.properties.values():
                if prop.linked and link in prop.linked:
                    prop.linked.remove(link)
                    id = prop.value_id
                    rec = session.query(Value).where(Value.id == id).one_or_none()
                    if rec:
                        rec.linked = ','.join(prop.linked)

        session.commit()


def getHistory(name:str, dt_begin:datetime = None, dt_end:datetime = None, limit:int = None, order_desc: bool = False, func=None) -> list:
    """Get history records for a property.

    Args:
        name (str): Qualified name ``Object.Property``.
        dt_begin (datetime, optional): Start of range (local time).
            Defaults to None.
        dt_end (datetime, optional): End of range (local time).
            Defaults to None.
        limit (int, optional): Maximum number of rows. Defaults to None.
        order_desc (bool, optional): If True, newest first. Defaults to False.
        func (callable, optional): Post-process each row. Defaults to None.

    Returns:
        list: History rows from ``ObjectManager.getHistory``.
            None if ``name`` is invalid, the object is missing, or on error.
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
    """Aggregate property history over a time range.

    Args:
        name (str): Qualified name ``Object.Property``.
        dt_begin (datetime, optional): Start of range (local time).
            Defaults to None.
        dt_end (datetime, optional): End of range (local time).
            Defaults to None.
        func (str, optional): Aggregate name: ``min``, ``max``, ``sum``,
            ``avg``, or ``count``. Defaults to None (implementation default).

    Returns:
        Any: Aggregate result from ``ObjectManager.getHistoryAggregate``.
            None if ``name`` is invalid, the object is missing, or on error.
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
    """Create or update a custom function definition in the database.

    Reloads the function in ``custom_function_registry`` after commit.

    Args:
        name (str): Function name.
        code (str, optional): Executable code. Defaults to ``''`` on create.
        test_code (str, optional): Test harness code. Defaults to ``''`` on
            create.
        description (str, optional): Description. Defaults to ``''`` on create.
        order (int, optional): Sort order. Defaults to 0 on create.
        active (bool, optional): Whether the function is active. Defaults to
            True on create.
        update (bool, optional): If True, update an existing row. If False and
            the name exists, returns False. Defaults to False.

    Returns:
        bool: True on success, False if the function exists and ``update`` is
            False.
    """
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
    """Delete a custom function from the database.

    Args:
        name (str): Function name.

    Returns:
        bool: True if deleted, False if not found.
    """
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
    """List custom functions with compile-error metadata.

    Returns:
        list[dict]: One dict per function with keys ``name``, ``description``,
            ``active``, ``order``, ``has_error``, ``error``.
    """
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
    """Execute test code for a custom function.

    Args:
        name (str): Custom function name (must exist in DB).
        test_code (str, optional): Code to run; if None, uses the stored
            ``test_code`` for ``name``. Defaults to None.
        params (Any, optional): Value passed to the test as ``params``.
            Defaults to None.

    Returns:
        tuple[str, bool]: ``(output, success)`` where ``output`` is captured
            stdout or an error message, and ``success`` is True when execution
            finished without error.
    """
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
