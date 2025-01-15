import datetime
from app.database import row2dict, session_scope
from app.core.main.ObjectManager import ObjectManager, PropertyManager, MethodManager
from app.core.models.Clasess import Class, Property, Method, Object, Value

class ObjectStorage():
    def __init__(self):
        self.objects = {}
        self.stats = {}

    def getObjectByName(self, name: str) -> ObjectManager:
        if name in self.objects:
            self.stats[name]['count_get'] = self.stats[name]['count_get'] + 1
            self.stats[name]['last_get'] = datetime.datetime.now()
            return self.objects[name]
        with session_scope() as session:
            obj = session.query(Object).filter_by(name=name).one_or_none()
            if obj:
                self.objects[obj.name] = self.createObjectManager(session, obj)
                self.stats[obj.name] = {'count_get':1, 'last_get': datetime.datetime.now()}
                return self.objects[name]
            # TODO warning
            return None
        
    def delObjectByName(self, name: str):
        del self.objects[name]

    def items(self):
        return self.objects.items()
    
    def values(self):
        return self.objects.values()
    
    def getStats(self):
        stats = {}
        for name,obj in self.objects.items():
            count_read = 0
            count_write = 0
            count_exec = 0
            stat_obj = obj.getStats()
            for _,prop in stat_obj["stat_properties"].items():
                count_read = count_read + prop['count_read']
                count_write = count_write + prop['count_write']
            for _,method in stat_obj["stat_methods"].items():
                count_exec = count_exec + method['count_executed']
            stats[name] = {
                'id': obj.object_id,
                'name': obj.name,
                'description': obj.description,
                'getObject':self.stats[name]['count_get'],
                'lastGetObject':self.stats[name]['last_get'],
                'getProperty':count_read,
                'setProperty':count_write,
                'callMethod':count_exec,
            }
        return stats

    def getAdvancedStats(self):
        stats = {}
        for name,obj in self.objects.items():
            stats[name] = {
                'id': obj.object_id,
                'name': obj.name,
                'description': obj.description,
                'count_get':self.stats[name]['count_get'],
                'last_get':self.stats[name]['last_get'],
                **self.stats[name],
                **obj.getStats()
            }
        return stats

    def methodsSort(self, methods):
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

    def createObjectManager(self, session, obj):
        om = ObjectManager(obj)
        # load properties
        properties = self.getPropertiesClass(session, obj.class_id, [])
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
        methods = self.getMethodsClass(session, obj.class_id, [])
        methods = methods + session.query(Method).filter(Method.object_id == obj.id).all()
        group_methods = {}
        for method in methods:
            if method.name not in group_methods:
                group_methods[method.name] = []
            group_methods[method.name].append(method)
        for _, group in group_methods.items():
            if len(group) > 1:
                group = self.methodsSort(group)
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
            om.template = self.getTemplateClass(obj.class_id)

        return om

    def getPropertiesClass(self, session, id, properties):
        if id:
            props = session.query(Property).filter(Property.class_id == id).all()
            properties = properties + props
            cls = session.query(Class).filter(Class.id == id).one_or_none()
            if cls and cls.parent_id:
                return self.getPropertiesClass(session, cls.parent_id, properties)
        return properties

    def getMethodsClass(self, session, id, methods):
        if id:
            meth = session.query(Method).filter(Method.class_id == id).all()
            methods = meth + methods
            cls = session.query(Class).filter(Class.id == id).one_or_none()
            if cls and cls.parent_id:
                return self.getMethodsClass(session, cls.parent_id, methods)
        return methods

    def getTemplateClass(self, class_id):
        with session_scope() as session:
            cls = session.query(Class).filter(Class.id == class_id).one_or_none()
            if cls and cls.template:
                return cls.template
            if cls and cls.parent_id:
                return self.getTemplateClass(cls.parent_id)
            return None

    # remove object
    def remove_object(self, object_name):
        if object_name in self.objects:
            del self.objects[object_name]

    def remove_objects_by_class(self, class_id):
        with session_scope() as session:
            objs = session.query(Object).filter(Object.class_id == class_id).all()
            for obj in objs:
                del self.objects[obj.name]
            childs = session.query(Class).filter(Class.parent_id == class_id).all()
            for child in childs:
                self.remove_objects_by_class(child.id)

    # reload object
    def reload_object(self, object_id):
        with session_scope() as session:
            obj = session.query(Object).filter(Object.id == object_id).one_or_none()
            if obj:
                del self.objects[obj.name]

    def reload_objects_by_class(self, class_id):
        with session_scope() as session:
            objs = session.query(Object).filter(Object.class_id == class_id).order_by(Object.name).all()
            for obj in objs:
                del self.objects[obj.name]
            childs = session.query(Class).filter(Class.parent_id == class_id).all()
            for child in childs:
                self.reload_objects_by_class(child.id)

    # preload all storage objects
    def preload_objects(self, ):
        with session_scope() as session:
            objs = session.query(Object).order_by(Object.name).all()
            for obj in objs:
                if obj.name not in self.objects:
                    self.objects[obj.name] = self.createObjectManager(session, obj)
                    if obj.name not in self.stats:
                        self.stats[obj.name] = {'count_get':1, 'last_get': datetime.datetime.now()}

    def clear(self):
        self.objects.clear()
        self.stats.clear()


objects_storage = ObjectStorage()
