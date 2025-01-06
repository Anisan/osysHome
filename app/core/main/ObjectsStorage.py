from app.database import row2dict, session_scope
from app.core.main.ObjectManager import ObjectManager, PropertyManager, MethodManager
from app.core.models.Clasess import Class, Property, Method, Object, Value

objects = {}

def methodsSort(methods):
    """Sort methods by hierarchy

    Args:
        methods (list[Method]): List of methods

    Returns:
        list[Method]: Sorted list of methods
    """
    result = []
    for method in methods[:]:
        if method.call_parent is None or method.call_parent == -1:
            result.append(method)
        elif method.call_parent == 0:
            result = []
            result.append(method)
        elif method.call_parent == 1:
            result.insert(-1, method)
    return result


def createObjectManager(session, obj):
    om = ObjectManager(obj)
    # load properties
    properties = getPropertiesClass(session, obj.class_id, [])
    property_obj = session.query(Property).filter(Property.object_id == obj.id).all()
    properties = properties + property_obj
    for prop in properties:
        value = session.query(Value).filter(Value.object_id == obj.id, Value.name == prop.name).first()
        # value = values[0]
        # if len(values) > 1:
        #   logger.warning("Warning! More than one value with same name and object id")
        #   db.session.query(Value).filter(Value.object_id == obj.id, Value.name == property.name).filter(Value.id != value.id).delete()
        #   db.session.commit()

        pm = PropertyManager(prop, value)
        if prop.method_id:
            method = session.query(Method).filter(Method.id == prop.method_id).one_or_none()
            pm.bindMethod(method.name)
        om._addProperty(pm)
    # load methods
    methods = getMethodsClass(session, obj.class_id, [])
    methods = methods + session.query(Method).filter(Method.object_id == obj.id).all()
    group_methods = {}
    for method in methods:
        if method.name not in group_methods:
            group_methods[method.name] = []
        group_methods[method.name].append(method)
    for _, group in group_methods.items():
        if len(group) > 1:
            group = methodsSort(group)
        group = [row2dict(item) for item in group]
        for item in group:
            if item['class_id']:
                cls = session.query(Class).filter(Class.id == item['class_id']).one_or_none()
                if cls:
                    item['owner'] = cls.name
            else:
                item['owner'] = obj.name
        mm = MethodManager(group)
        om._addMethod(mm)

    # get template from class
    if not obj.template:
        om.template = getTemplateClass(obj.class_id)

    return om

def getPropertiesClass(session, id, properties):
    if id:
        props = session.query(Property).filter(Property.class_id == id).all()
        properties = properties + props
        cls = session.query(Class).filter(Class.id == id).one_or_none()
        if cls and cls.parent_id:
            return getPropertiesClass(session, cls.parent_id, properties)
    return properties

def getMethodsClass(session, id, methods):
    if id:
        meth = session.query(Method).filter(Method.class_id == id).all()
        methods = meth + methods
        cls = session.query(Class).filter(Class.id == id).one_or_none()
        if cls and cls.parent_id:
            return getMethodsClass(session, cls.parent_id, methods)
    return methods

def getTemplateClass(class_id):
    with session_scope() as session:
        cls = session.query(Class).filter(Class.id == class_id).one_or_none()
        if cls and cls.template:
            return cls.template
        if cls and cls.parent_id:
            return getTemplateClass(cls.parent_id)
        return None

# remove object
def remove_object(object_name):
    global objects
    if object_name in objects:
        del objects[object_name]

def remove_objects_by_class(class_id):
    global objects
    with session_scope() as session:
        objs = session.query(Object).filter(Object.class_id == class_id).all()
        for obj in objs:
            del objects[obj.name]

# reload object
def reload_object(object_id):
    global objects
    with session_scope() as session:
        obj = session.query(Object).filter(Object.id == object_id).one_or_none()
        if obj:
            objects[obj.name] = createObjectManager(session, obj)

def reload_objects_by_class(class_id):
    global objects
    with session_scope() as session:
        objs = session.query(Object).filter(Object.class_id == class_id).order_by(Object.name).all()
        for obj in objs:
            objects[obj.name] = createObjectManager(session, obj)

# init storage objects
def init_objects():
    global objects
    with session_scope() as session:
        objs = session.query(Object).order_by(Object.name).all()
        for obj in objs:
            objects[obj.name] = createObjectManager(session, obj)
