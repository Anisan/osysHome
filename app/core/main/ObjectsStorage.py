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
import threading
from contextlib import nullcontext
from datetime import datetime
from app.configuration import Config
from app.database import row2dict, session_scope, get_now_to_utc
from app.core.main.ObjectManager import ObjectManager, PropertyManager, MethodManager
from app.core.models.Clasess import Class, Property, Method, Object, Value, History
from app.logging_config import getLogger
from app.core.main.PluginsHelper import plugins


class _RuntimeObjectMap(dict):
    """Runtime cache map; full enumeration syncs missing objects from DB."""

    __slots__ = ("_storage",)

    def __init__(self, storage: "ObjectStorage"):
        super().__init__()
        self._storage = storage

    def _sync_for_enumeration(self) -> None:
        self._storage.sync_missing()

    def keys(self):
        self._sync_for_enumeration()
        return super().keys()

    def values(self):
        self._sync_for_enumeration()
        return super().values()

    def items(self):
        self._sync_for_enumeration()
        return super().items()

    def __iter__(self):
        self._sync_for_enumeration()
        return super().__iter__()

    def __len__(self):
        self._sync_for_enumeration()
        return super().__len__()


class ObjectStorage():
    def __init__(self):
        self.logger = getLogger('object_storage')
        self.objects = _RuntimeObjectMap(self)
        self.stats = {}
        self.name_lock_global = threading.Lock()
        self.name_lock = {}
        self.clean_objects = {}

        self._stop_event = threading.Event()
        self._preload_stop_event = threading.Event()
        self._preload_thread = None
        self.cleaner_thread = threading.Thread(target=self.clean_task, daemon=True)
        self.cleaner_thread.start()

    def _invoke_lifecycle(self, om: ObjectManager, hook: str) -> None:
        if hook not in om.methods or om._lifecycle_running:
            return
        om._lifecycle_running = True
        try:
            om.callMethod(hook, source=f"system:{hook}")
        except Exception:
            self.logger.exception("Lifecycle hook %s failed for object %s", hook, om.name)
        finally:
            om._lifecycle_running = False

    def invoke_lifecycle_all(self, hook: str) -> None:
        for _, om in list(dict.items(self.objects)):
            self._invoke_lifecycle(om, hook)

    def _replace_object_manager(self, session, obj: Object) -> ObjectManager:
        old_om = self.objects.get(obj.name)
        if old_om:
            self._invoke_lifecycle(old_om, "onStop")
        om = self._createObjectManager(session, obj)
        self.objects[obj.name] = om
        om.clear_runtime()
        self._invoke_lifecycle(om, "onInit")
        return om

    def _load_or_reload_object(self, session, obj: Object) -> ObjectManager:
        if obj.name in self.objects:
            om = self._replace_object_manager(session, obj)
        else:
            om = self._createObjectManager(session, obj)
            self.objects[obj.name] = om
            self._invoke_lifecycle(om, "onInit")
        if obj.name not in self.stats:
            self.stats[obj.name] = {
                'count_get': 1,
                'last_get': get_now_to_utc(),
            }
        if obj.name in self.clean_objects:
            del self.clean_objects[obj.name]
        return om

    def clean_task(self):

        while not self._stop_event.is_set():
            try:
                now = datetime.now()

                object_keys = list(dict.keys(self.objects))
                if not object_keys:
                    self._stop_event.wait(60)
                    continue

                self.logger.debug("Check objects for clean history")

                for key, obj in dict.items(self.objects):
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
                    om = self._createObjectManager(session, obj)
                    self.objects[obj.name] = om
                    self.stats[obj.name] = {'count_get':1, 'last_get': get_now_to_utc()}
                    self._invoke_lifecycle(om, "onInit")
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
                if method:
                    pm.bindMethod(method.name)
                else:
                    self.logger.warning(
                        "Property %s.%s references missing method id %s",
                        obj.name, prop.name, prop.method_id,
                    )
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
            self._invoke_lifecycle(self.objects[object_name], "onStop")
            del self.objects[object_name]
            if object_name in self.stats:
                del self.stats[object_name]
            if object_name in self.clean_objects:
                del self.clean_objects[object_name]

    def rename_object(self, old_name: str, new_name: str, object_id: int) -> None:
        self.logger.debug(f"Rename object - {old_name} -> {new_name}")
        if old_name in self.objects:
            self._invoke_lifecycle(self.objects[old_name], "onStop")
            del self.objects[old_name]
        if old_name in self.stats:
            del self.stats[old_name]
        if old_name in self.clean_objects:
            del self.clean_objects[old_name]
        self.reload_object(object_id)
        self.changeObject("rename", old_name, None, None, new_name)

    def remove_objects_by_class(self, class_id):
        self.logger.debug(f"Remove objects by class - id:{class_id}")
        with session_scope() as session:
            objs = session.query(Object).filter(Object.class_id == class_id).all()
            for obj in objs:
                self.remove_object(obj.name)
            childs = session.query(Class).filter(Class.parent_id == class_id).all()
            for child in childs:
                self.remove_objects_by_class(child.id)

    def sync_missing(self) -> int:
        """Load objects that exist in DB but are not yet in runtime cache."""
        loaded = 0
        with session_scope() as session:
            objs = session.query(Object).order_by(Object.name).all()
            for obj in objs:
                if obj.name in self.objects:
                    continue
                om = self._createObjectManager(session, obj)
                self.objects[obj.name] = om
                if obj.name not in self.stats:
                    self.stats[obj.name] = {'count_get': 1, 'last_get': get_now_to_utc()}
                self._invoke_lifecycle(om, "onInit")
                loaded += 1
        if loaded:
            self.logger.debug("Synced %s missing object(s) into runtime cache", loaded)
        return loaded

    def sync_removed(self) -> int:
        """Evict cached objects that were deleted from DB."""
        with session_scope() as session:
            db_names = {name for (name,) in session.query(Object.name).all()}
        removed = 0
        for name in list(dict.keys(self.objects)):
            if name not in db_names:
                self.remove_object(name)
                removed += 1
        if removed:
            self.logger.debug("Evicted %s stale object(s) from runtime cache", removed)
        return removed

    def sync_cache(self) -> None:
        """Align runtime cache with DB: evict deleted, load missing."""
        self.sync_removed()
        self.sync_missing()

    # reload object
    def reload_object(self, object_id):
        self.logger.debug(f"Reload object - id:{object_id}")
        with session_scope() as session:
            obj = session.query(Object).filter(Object.id == object_id).one_or_none()
            if obj:
                self._load_or_reload_object(session, obj)

    def reload_objects_by_class(self, class_id):
        self.logger.debug(f"Reload objects by class - id:{class_id}")
        with session_scope() as session:
            objs = session.query(Object).filter(Object.class_id == class_id).order_by(Object.name).all()
            for obj in objs:
                self._load_or_reload_object(session, obj)
            childs = session.query(Class).filter(Class.parent_id == class_id).all()
            for child in childs:
                self.reload_objects_by_class(child.id)

    # preload all storage objects
    def preload_objects(self):
        self.sync_missing()

    def start_background_preload(self, app=None) -> None:
        if not Config.OBJECT_PRELOAD_ENABLED:
            return
        if self._preload_thread and self._preload_thread.is_alive():
            return
        self._preload_stop_event.clear()
        self._preload_thread = threading.Thread(
            target=self._background_preload_worker,
            args=(app,),
            daemon=True,
            name="ObjectPreload",
        )
        self._preload_thread.start()

    def stop_background_preload(self) -> None:
        self._preload_stop_event.set()
        thread = self._preload_thread
        if thread and thread.is_alive():
            thread.join(timeout=5.0)

    def _background_preload_worker(self, app) -> None:
        ctx = app.app_context() if app is not None else nullcontext()
        batch_size = Config.OBJECT_PRELOAD_BATCH_SIZE or 10
        interval = Config.OBJECT_PRELOAD_INTERVAL_SEC or 0.5
        try:
            with ctx:
                with session_scope() as session:
                    names = [o.name for o in session.query(Object).order_by(Object.name).all()]
                total = len(names)
                for i in range(0, total, batch_size):
                    if self._preload_stop_event.is_set():
                        break
                    batch = names[i:i + batch_size]
                    for name in batch:
                        if self._preload_stop_event.is_set():
                            break
                        if name in self.objects:
                            continue
                        self.getObjectByName(name)
                    preloaded = sum(1 for n in names if n in self.objects)
                    self.logger.info("Preloaded %s/%s objects", preloaded, total)
                    if self._preload_stop_event.wait(interval):
                        break
        except Exception:
            self.logger.exception("Background object preload failed")

    def clear(self):
        self.logger.info("Clear storage")
        dict.clear(self.objects)
        self.stats.clear()
        self.sync_cache()

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
