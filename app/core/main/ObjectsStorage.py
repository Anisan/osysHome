import threading
from datetime import datetime
from app.database import row2dict, session_scope, get_now_to_utc
from app.core.main.ObjectManager import ObjectManager, PropertyManager, MethodManager
from app.core.models.Clasess import Class, Property, Method, Object, Value, History
from app.logging_config import getLogger
from app.core.main.PluginsHelper import plugins

"""
A class for managing objects storage with thread-safe operations.

This class provides functionality to store, retrieve, clean, and manage objects with their properties and methods.
It includes background cleaning of object history, object locking mechanism for thread safety,
and various statistics collection about object usage.

Attributes:
    logger (Logger): Logger instance for logging operations.
    objects (dict): Dictionary storing object managers.
    stats (dict): Dictionary storing statistics about object usage.
    name_lock (dict): Dictionary storing threading conditions for object locking.
    clean_objects (dict): Dictionary storing cleaning information for objects.
    _stop_event (threading.Event): Event to control the cleaning thread.
    cleaner_thread (threading.Thread): Thread for periodic cleaning of object history.

The class provides methods for:
- Getting objects by name with thread-safe locking
- Managing object cleaning and statistics
- Handling object permissions
- Creating and managing object managers
- Loading and reloading objects
- Clearing storage
- Handling object change events

Note:
    This class is designed to be thread-safe and includes background maintenance tasks.
"""
class ObjectStorage():
    def __init__(self):
        self.logger = getLogger('object_storage')
        self.objects = {}
        self.stats = {}
        self.name_lock_global = threading.Lock()
        self.name_lock = {}
        self.clean_objects = {}

        self._stop_event = threading.Event()
        self.cleaner_thread = threading.Thread(target=self.clean_task, daemon=True)
        self.cleaner_thread.start()

    def clean_task(self):

        while not self._stop_event.is_set():
            try:
                now = datetime.now()

                object_keys = list(self.objects.keys())
                if not object_keys:
                    self._stop_event.wait(60)
                    continue

                self.logger.debug("Check objects for clean history")

                for key,obj in self.objects.items():
                    if self.clean_objects.get(key) is None or now.date() > self.clean_objects.get(key,{}).get("dt").date():
                        res = obj.cleanHistory()
                        count_deleted = 0
                        for name, item in res.items():
                            if item["deleted"] > 0:
                                self.logger.info(f'Clean history {key}.{name} (history - {item["history"]} days). Count deleted:{item["deleted"]}')
                            count_deleted += item["deleted"]
                        self.clean_objects[key] = {"dt": now, "count": count_deleted, "result":res}
                        break
            except Exception as e:
                self.logger.exception(f'Error in clean task: {e}', exc_info=True)
            self._stop_event.wait(60.0)

    def getObjectByName(self, name: str) -> ObjectManager:
        with self.name_lock_global:
            if name not in self.name_lock:
                self.name_lock[name] = threading.Condition()
            condition = self.name_lock[name]

        with condition:
            if name in self.objects:
                self.stats[name]['count_get'] = self.stats[name]['count_get'] + 1
                self.stats[name]['last_get'] = get_now_to_utc()
                return self.objects[name]

            with session_scope() as session:
                obj = session.query(Object).filter_by(name=name).one_or_none()
                if obj:
                    self.objects[obj.name] = self._createObjectManager(session, obj)
                    self.stats[obj.name] = {'count_get':1, 'last_get': get_now_to_utc()}
                    condition.notify_all()
                    return self.objects[name]

            self.logger.warning(f'Object "{name}" not found')
            return None

    def items(self):
        return self.objects.items()

    def values(self):
        return self.objects.values()

    def getCleanerStat(self):
        stats = []
        for key, item in self.clean_objects.items():
            obj = self.getObjectByName(key)
            stats.append({
                'id': obj.object_id,
                'name': obj.name,
                'description': obj.description,
                'cleared':item["dt"],
                'count':item["count"],
                'details': item["result"]
            })
        return stats

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

    def merge_dicts(self, dict1, dict2):
        """
        Рекурсивно объединяет два словаря.
        При совпадении ключей значение берется из второго словаря.
        Если значения являются словарями, они объединяются рекурсивно.
        """
        if dict1 is None:
            return dict2
        if dict2 is None:
            return dict1
        result = dict1.copy()  # Создаем копию первого словаря
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Если ключ есть в обоих словарях и значения — это словари, объединяем рекурсивно
                result[key] = self.merge_dicts(result[key], value)
            else:
                # Иначе берем значение из второго словаря
                result[key] = value
        return result

    def get_permissions(self, om:ObjectManager):
        name = om.__dict__.get('name')
        if '_permissions' not in self.objects:
            return None
        _objectPermissions = self.objects['_permissions']
        if 'properties' not in _objectPermissions.__dict__:
            return None

        _permissions = None
        properties_dict = _objectPermissions.__dict__.get('properties', {})
        key = "object:*"
        if key in properties_dict:
            property_manager = properties_dict[key]
            _permissions = property_manager.__dict__.get('_PropertyManager__value')
        for className in om.__dict__.get('parents',[]):
            _permissionsClass = None
            key = "class:" + className
            if key in properties_dict:
                property_manager = properties_dict[key]
                _permissionsClass = property_manager.__dict__.get('_PropertyManager__value')
            if _permissionsClass:
                _permissions = self.merge_dicts(_permissions, _permissionsClass)
        _permissionsObject = None
        key = "object:" + name
        if key in properties_dict:
            property_manager = properties_dict[key]
            _permissionsObject = property_manager.__dict__.get('_PropertyManager__value')
        if _permissionsObject:
            _permissions = self.merge_dicts(_permissions, _permissionsObject)

        return _permissions

    def _createObjectManager(self, session, obj):
        """Create object manager for given object
        Args:
        session (Session): Session object
        obj (Object): Object to create object manager for
        Returns:
        ObjectManager: Object manager for given object
        """
        self.logger.debug(f"Create object manager - {obj.name}")
        om = ObjectManager(obj)
        # load properties
        properties = self._getPropertiesClass(session, obj.class_id, [])
        property_obj = session.query(Property).filter(Property.object_id == obj.id).all()
        properties = properties + property_obj
        for prop in properties:
            values = session.query(Value).filter(Value.object_id == obj.id, Value.name == prop.name).all()
            if values:
                value = values[0]
                if len(values) > 1:
                    self.logger.warning(f"Warning! More than one value with same name and object id. {obj.name}.{prop.name}")
                    for item in values[1:]:
                        # move history
                        session.query(History).filter(History.value_id == item.id).update({History.value_id: value.id}, synchronize_session='fetch')
                        # delete clone
                        session.query(Value).filter(Value.id == item.id).delete()
                    session.commit()
                    self.logger.info(f"Fixed! Remove dublicate {obj.name}.{prop.name}")
            else:
                value = None

            pm = PropertyManager(obj.id, prop, value)
            if prop.method_id:
                method = session.query(Method).filter(Method.id == prop.method_id).one_or_none()
                pm.bindMethod(method.name)
            om._addProperty(pm)
        # load methods
        methods = self._getMethodsClass(session, obj.class_id, [])
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

        # get templates from class
        templates = self._getTemplateClass(session, obj.class_id,{})
        templates[obj.name] = obj.template
        om._setTemplates(templates)

        parents = []
        parents = self._getParents(session, obj.class_id, parents)
        om.parents = parents
        om.set_permission(self.get_permissions(om))
        return om

    def _getParents(self, session, id, parents):
        if id:
            cls = session.query(Class).filter(Class.id == id).one_or_none()
            if cls:
                parents.append(cls.name)
                if cls.parent_id:
                    return self._getParents(session, cls.parent_id, parents)
        return parents

    def _getPropertiesClass(self, session, id, properties):
        if id:
            props = session.query(Property).filter(Property.class_id == id).all()
            properties = properties + props
            cls = session.query(Class).filter(Class.id == id).one_or_none()
            if cls and cls.parent_id:
                return self._getPropertiesClass(session, cls.parent_id, properties)
        return properties

    def _getMethodsClass(self, session, id, methods):
        if id:
            meth = session.query(Method).filter(Method.class_id == id).all()
            methods = meth + methods
            cls = session.query(Class).filter(Class.id == id).one_or_none()
            if cls and cls.parent_id:
                return self._getMethodsClass(session, cls.parent_id, methods)
        return methods

    def _getTemplateClass(self, session, id, templates):
        if id:
            cls = session.query(Class).filter(Class.id == id).one_or_none()
            templates[cls.name] = cls.template
            if cls and cls.parent_id:
                return self._getTemplateClass(session, cls.parent_id, templates)
        return templates

    # remove object
    def remove_object(self, object_name):
        self.logger.debug(f"Remove object - name:{object_name}")
        if object_name in self.objects:
            del self.objects[object_name]
            if object_name in self.clean_objects:
                del self.clean_objects[object_name]

    def remove_objects_by_class(self, class_id):
        self.logger.debug(f"Remove objects by class - id:{class_id}")
        with session_scope() as session:
            objs = session.query(Object).filter(Object.class_id == class_id).all()
            for obj in objs:
                if obj.name in self.objects:
                    del self.objects[obj.name]
                    if obj.name in self.clean_objects:
                        del self.clean_objects[obj.name]
            childs = session.query(Class).filter(Class.parent_id == class_id).all()
            for child in childs:
                self.remove_objects_by_class(child.id)

    # reload object
    def reload_object(self, object_id):
        self.logger.debug(f"Reload object - id:{object_id}")
        with session_scope() as session:
            obj = session.query(Object).filter(Object.id == object_id).one_or_none()
            if obj:
                if obj.name in self.objects:
                    del self.objects[obj.name]
                    if obj.name in self.clean_objects:
                        del self.clean_objects[obj.name]

    def reload_objects_by_class(self, class_id):
        self.logger.debug(f"Reload objects by class - id:{class_id}")
        with session_scope() as session:
            objs = session.query(Object).filter(Object.class_id == class_id).order_by(Object.name).all()
            for obj in objs:
                if obj.name in self.objects:
                    del self.objects[obj.name]
                    if obj.name in self.clean_objects:
                        del self.clean_objects[obj.name]
            childs = session.query(Class).filter(Class.parent_id == class_id).all()
            for child in childs:
                self.reload_objects_by_class(child.id)

    # preload all storage objects
    def preload_objects(self):
        with session_scope() as session:
            objs = session.query(Object).order_by(Object.name).all()
            for obj in objs:
                if obj.name not in self.objects:
                    self.objects[obj.name] = self._createObjectManager(session, obj)
                    if obj.name not in self.stats:
                        self.stats[obj.name] = {'count_get':1, 'last_get': get_now_to_utc()}

    def clear(self):
        self.logger.info("Clear storage")
        self.objects.clear()
        self.stats.clear()

    def changeObject(self, event, object_name, property_name, method_name, new_value):
        # send event to plugins
        self.logger.info(f"Change object event: {event} Object:{object_name} Property:{property_name} Method:{method_name} New value:{new_value}")
        for _,plugin in plugins.items():
            plugin_obj = plugin["instance"]
            if hasattr(plugin_obj, "changeObject"):
                try:
                    plugin["instance"].changeObject(event, object_name, property_name, method_name, new_value)
                except Exception as ex:
                    self.logger.exception(ex)


objects_storage = ObjectStorage()
