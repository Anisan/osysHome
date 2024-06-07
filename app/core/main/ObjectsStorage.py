from .ObjectManager import  ObjectManager, PropertyManager, MethodManager
from ..models.Clasess import Class, Property, Method, Object, Value

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
        if not method.call_parent or method.call_parent == -1:
            result.append(method)
        elif method.call_parent == 0:
            result = []
            result.append(method)
        elif method.call_parent == 1:
            result.insert(-1, method)
    return result


def createObjectManager(obj):
    om = ObjectManager(obj)
    # load properties
    properties = getPropertiesClassFromCache(obj.class_id)
    property_obj = Property.query.filter(Property.object_id == obj.id).all()
    properties = properties + property_obj
    for prop in properties:
        value = Value.query.filter(Value.object_id == obj.id, Value.name == prop.name).first()
        #value = values[0]
        #if len(values) > 1:
        #    logger.warning("Warning! More than one value with same name and object id")
            #db.session.query(Value).filter(Value.object_id == obj.id, Value.name == property.name).filter(Value.id != value.id).delete()
            #db.session.commit()

        pm = PropertyManager(prop, value)
        if prop.method_id:
            method = Method.query.filter(Method.id == prop.method_id).one_or_none()
            pm.bindMethod(method.name)
        om.addProperty(pm)
    # load methods
    methods = getMethodsClassFromCache(obj.class_id)
    methods = methods + Method.query.filter(Method.object_id == obj.id).all()
    group_methods = {}
    for method in methods:
        if method.name not in group_methods:
            group_methods[method.name] = []
        group_methods[method.name].append(method)
    for _, group in group_methods.items():
        if len(group) > 1:
            group = methodsSort(group)

    for _, group in group_methods.items():
        mm = MethodManager(group)
        om.addMethod(mm)

    # get template from class
    if not obj.template:
        om.template = getTemplateClass(obj.class_id)

    return om

cachePropertiesClasses = {}
cacheMethodsClasses = {}

def getPropertiesClass(id, properties):
    props = Property.query.filter(Property.class_id==id).all()
    properties = properties + props
    cls = Class.get_by_id(id)
    if cls.parent_id:
        return getPropertiesClass(cls.parent_id, properties)
    return properties

def getPropertiesClassFromCache(id):
    global cachePropertiesClasses
    ##if id in cachePropertiesClasses:
    ##    return cachePropertiesClasses[id]
    properties = []
    properties = getPropertiesClass(id, properties)
    cachePropertiesClasses[id] = properties
    return properties

def getMethodsClass(id, methods):
    meth = Method.query.filter(Method.class_id==id).all()
    methods = meth + methods
    cls = Class.get_by_id(id)
    if cls.parent_id:
        return getMethodsClass(cls.parent_id, methods)
    return methods

def getMethodsClassFromCache(id):
    global cacheMethodsClasses
   ## if id in cacheMethodsClasses:
   ##     return cacheMethodsClasses[id]
    methods = []
    methods = getMethodsClass(id, methods)
    cacheMethodsClasses[id] = methods
    return methods

def getTemplateClass(class_id):
    cls = Class.get_by_id(class_id)
    if cls.template:
        return cls.template
    if cls.parent_id:
        return getTemplateClass(cls.parent_id)
    return None


# remove object
def remove_object(object_name):
    global objects
    if object_name in objects:
        del objects[object_name]

def remove_objects_by_class(class_id):
    global objects
    global cachePropertiesClasses
    global cacheMethodsClasses
    if class_id in cachePropertiesClasses:
        del cachePropertiesClasses[class_id]
    if class_id in cacheMethodsClasses:
        del cacheMethodsClasses[class_id]
    objs = Object.query.filter(Object.class_id == class_id).all()
    for obj in objs:
        del objects[obj.name]

# reload object
def reload_object(object_id):
    global objects
    obj = Object.get_by_id(object_id)
    if obj:
        objects[obj.name] = createObjectManager(obj)

def reload_objects_by_class(class_id):
    global objects
    global cachePropertiesClasses
    global cacheMethodsClasses
    if class_id in cachePropertiesClasses:
        del cachePropertiesClasses[class_id]
    if class_id in cacheMethodsClasses:
        del cacheMethodsClasses[class_id]
    objs = Object.query.filter(Object.class_id == class_id).order_by(Object.name).all()
    for obj in objs:
        objects[obj.name] = createObjectManager(obj)

# init storage objects
def init_objects():
    global objects
    objs = Object.query.order_by(Object.name).all()
    for obj in objs:
        objects[obj.name] = createObjectManager(obj)
