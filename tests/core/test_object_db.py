"""Tests for app.core.lib.object_db helpers (in-memory SQLite)."""
import unittest
from unittest.mock import patch

from app.core.models.Clasess import Class, History, Method, Object, Property, Value
from app.core.lib.object_db import (
    cleanup_orphan_records,
    delete_object_from_db,
    delete_objects_by_class,
    get_descendant_class_ids,
    migrate_value_for_type_change,
    migrate_values_for_property_type_change,
)


class ObjectDbSQLiteTestCase(unittest.TestCase):
    """Базовый класс: Flask + SQLite :memory: для каждого теста."""

    def setUp(self):
        from flask import Flask
        from app.extensions import db

        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self.app)
        self.db = db
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.db.create_all()

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.ctx.pop()

    def _add_class(self, name, parent_id=None):
        cls = Class(name=name, description='', parent_id=parent_id)
        self.db.session.add(cls)
        self.db.session.flush()
        return cls

    def _add_object(self, name, class_id=None):
        obj = Object(name=name, description='', class_id=class_id)
        self.db.session.add(obj)
        self.db.session.flush()
        return obj

    def _add_full_object(self, name, class_id=None, *, with_value=True, with_history=True):
        obj = self._add_object(name, class_id)
        self.db.session.add(Property(name='temp', type='float', object_id=obj.id))
        self.db.session.add(Method(name='read', object_id=obj.id, code='pass'))
        if with_value:
            val = Value(object_id=obj.id, name='temp', value='23.5')
            self.db.session.add(val)
            self.db.session.flush()
            if with_history:
                self.db.session.add(History(value_id=val.id, value='23.0'))
        self.db.session.commit()
        return obj

    def _add_value(self, object_id, name, value, *, with_history=False, history_value=None):
        val = Value(object_id=object_id, name=name, value=value)
        self.db.session.add(val)
        self.db.session.flush()
        if with_history:
            self.db.session.add(History(value_id=val.id, value=history_value or value))
        return val

    def _table_counts(self):
        return {
            'classes': Class.query.count(),
            'objects': Object.query.count(),
            'properties': Property.query.count(),
            'methods': Method.query.count(),
            'values': Value.query.count(),
            'history': History.query.count(),
        }


class TestMigrateValueForTypeChange(unittest.TestCase):
    """Чистые функции без БД."""

    def test_same_type_returns_original(self):
        self.assertEqual(migrate_value_for_type_change('int', 'int', '42'), '42')

    def test_empty_values_unchanged(self):
        self.assertIsNone(migrate_value_for_type_change('int', 'float', None))
        self.assertEqual(migrate_value_for_type_change('int', 'float', ''), '')
        self.assertEqual(migrate_value_for_type_change('int', 'float', 'None'), 'None')

    def test_int_to_float(self):
        self.assertEqual(migrate_value_for_type_change('int', 'float', '42'), '42.0')

    def test_float_to_int_truncates(self):
        self.assertEqual(migrate_value_for_type_change('float', 'int', '23.7'), '23')

    def test_str_to_bool(self):
        self.assertEqual(migrate_value_for_type_change('str', 'bool', 'yes'), 'True')
        self.assertEqual(migrate_value_for_type_change('str', 'bool', 'off'), 'False')

    def test_invalid_conversion_returns_none(self):
        self.assertIsNone(migrate_value_for_type_change('str', 'int', 'not-a-number'))


class TestGetDescendantClassIds(ObjectDbSQLiteTestCase):
    def test_returns_root_and_children(self):
        root = self._add_class('root')
        child_a = self._add_class('child_a', parent_id=root.id)
        child_b = self._add_class('child_b', parent_id=root.id)
        grandchild = self._add_class('grandchild', parent_id=child_a.id)
        self.db.session.commit()

        ids = get_descendant_class_ids(root.id)
        self.assertEqual(ids, [root.id, child_a.id, child_b.id, grandchild.id])

    def test_single_class_without_children(self):
        cls = self._add_class('solo')
        self.db.session.commit()

        self.assertEqual(get_descendant_class_ids(cls.id), [cls.id])


class TestDeleteObjectFromDb(ObjectDbSQLiteTestCase):
    def test_returns_none_when_object_missing(self):
        with patch('app.core.lib.object_db.clearScheduledJob') as mock_clear:
            self.assertIsNone(delete_object_from_db(999))
            self.db.session.commit()
            mock_clear.assert_not_called()

    @patch('app.core.lib.object_db.clearScheduledJob')
    def test_deletes_history_values_properties_methods_and_object(self, mock_clear):
        obj = self._add_full_object('sensor_a')
        object_id = obj.id

        self.assertEqual(Object.query.count(), 1)
        self.assertEqual(Property.query.filter(Property.object_id == object_id).count(), 1)
        self.assertEqual(Method.query.filter(Method.object_id == object_id).count(), 1)
        self.assertEqual(Value.query.filter(Value.object_id == object_id).count(), 1)
        self.assertEqual(History.query.count(), 1)

        name = delete_object_from_db(object_id)
        self.db.session.commit()

        self.assertEqual(name, 'sensor_a')
        self.assertEqual(Object.query.count(), 0)
        self.assertEqual(Property.query.filter(Property.object_id == object_id).count(), 0)
        self.assertEqual(Method.query.filter(Method.object_id == object_id).count(), 0)
        self.assertEqual(Value.query.filter(Value.object_id == object_id).count(), 0)
        self.assertEqual(History.query.count(), 0)
        mock_clear.assert_called_once_with('sensor_a\\_%')

    @patch('app.core.lib.object_db.clearScheduledJob')
    def test_deletes_object_without_values(self, mock_clear):
        obj = self._add_full_object('sensor_b', with_value=False)
        object_id = obj.id

        name = delete_object_from_db(object_id)
        self.db.session.commit()

        self.assertEqual(name, 'sensor_b')
        self.assertEqual(Object.query.count(), 0)
        self.assertEqual(Property.query.filter(Property.object_id == object_id).count(), 0)
        self.assertEqual(Method.query.filter(Method.object_id == object_id).count(), 0)
        self.assertEqual(Value.query.count(), 0)
        self.assertEqual(History.query.count(), 0)
        mock_clear.assert_called_once_with('sensor_b\\_%')

    @patch('app.core.lib.object_db.clearScheduledJob')
    def test_can_skip_schedule_cleanup(self, mock_clear):
        obj = self._add_full_object('sensor_c', with_value=False)
        delete_object_from_db(obj.id, clear_schedules=False)
        self.db.session.commit()

        self.assertEqual(Object.query.count(), 0)
        mock_clear.assert_not_called()

    @patch('app.core.lib.object_db.clearScheduledJob')
    def test_keeps_other_objects_and_their_data_intact(self, mock_clear):
        obj_a = self._add_full_object('sensor_a')
        obj_b = self._add_full_object('sensor_b')
        obj_c = self._add_full_object('sensor_c')
        self._add_value(obj_a.id, 'humidity', '55', with_history=True, history_value='54')
        self._add_value(obj_c.id, 'pressure', '1013', with_history=True, history_value='1012')
        self.db.session.commit()

        before = self._table_counts()
        self.assertEqual(before['objects'], 3)
        self.assertEqual(before['values'], 5)
        self.assertEqual(before['history'], 5)

        name = delete_object_from_db(obj_b.id)
        self.db.session.commit()

        self.assertEqual(name, 'sensor_b')
        after = self._table_counts()
        self.assertEqual(after['objects'], 2)
        self.assertEqual(after['properties'], 2)
        self.assertEqual(after['methods'], 2)
        self.assertEqual(after['values'], 4)
        self.assertEqual(after['history'], 4)

        self.assertIsNone(Object.query.filter(Object.name == 'sensor_b').first())
        self.assertIsNotNone(Object.query.filter(Object.name == 'sensor_a').first())
        self.assertIsNotNone(Object.query.filter(Object.name == 'sensor_c').first())
        self.assertEqual(
            Value.query.filter(Value.object_id == obj_a.id).count(), 2,
        )
        self.assertEqual(
            Value.query.filter(Value.object_id == obj_c.id).count(), 2,
        )
        self.assertEqual(Property.query.filter(Property.object_id == obj_b.id).count(), 0)
        self.assertEqual(Method.query.filter(Method.object_id == obj_b.id).count(), 0)
        mock_clear.assert_called_once_with('sensor_b\\_%')

    @patch('app.core.lib.object_db.clearScheduledJob')
    def test_keeps_class_level_definitions_when_object_deleted(self, _mock_clear):
        cls = self._add_class('devices')
        self.db.session.add(Property(name='class_temp', type='float', class_id=cls.id))
        self.db.session.add(Method(name='class_read', class_id=cls.id, code='pass'))
        obj = self._add_full_object('dev_1', class_id=cls.id)
        self.db.session.commit()

        delete_object_from_db(obj.id)
        self.db.session.commit()

        self.assertEqual(Class.query.count(), 1)
        self.assertEqual(Object.query.count(), 0)
        self.assertEqual(Property.query.filter(Property.class_id == cls.id).count(), 1)
        self.assertEqual(Method.query.filter(Method.class_id == cls.id).count(), 1)
        self.assertEqual(Property.query.filter(Property.object_id.isnot(None)).count(), 0)
    @patch('app.core.lib.object_db.clearScheduledJob')
    def test_deletes_objects_in_class_tree(self, _mock_clear):
        root = self._add_class('devices')
        child = self._add_class('sensors', parent_id=root.id)
        self._add_full_object('dev_1', class_id=root.id)
        self._add_full_object('dev_2', class_id=child.id)
        other = self._add_class('other')
        self._add_full_object('other_dev', class_id=other.id)
        self.db.session.commit()

        deleted = delete_objects_by_class(root.id)
        self.db.session.commit()

        self.assertEqual(sorted(deleted), ['dev_1', 'dev_2'])
        self.assertEqual(Object.query.count(), 1)
        self.assertEqual(Object.query.filter(Object.name == 'other_dev').count(), 1)
        self.assertEqual(Value.query.count(), 1)
        self.assertEqual(History.query.count(), 1)

    @patch('app.core.lib.object_db.clearScheduledJob')
    def test_keeps_unrelated_classes_objects_and_class_metadata(self, _mock_clear):
        root = self._add_class('devices')
        child = self._add_class('sensors', parent_id=root.id)
        other = self._add_class('lighting')
        standalone = self._add_class('standalone')

        self.db.session.add(Property(name='root_prop', type='int', class_id=root.id))
        self.db.session.add(Method(name='root_method', class_id=root.id, code='pass'))
        self.db.session.add(Property(name='other_prop', type='int', class_id=other.id))
        self.db.session.add(Method(name='other_method', class_id=other.id, code='pass'))

        self._add_full_object('dev_1', class_id=root.id)
        self._add_full_object('dev_2', class_id=child.id)
        kept = self._add_full_object('lamp_1', class_id=other.id)
        self._add_full_object('solo_1', class_id=standalone.id)
        self.db.session.commit()

        deleted = delete_objects_by_class(root.id)
        self.db.session.commit()

        self.assertEqual(sorted(deleted), ['dev_1', 'dev_2'])
        self.assertEqual(Object.query.count(), 2)
        self.assertEqual(set(o.name for o in Object.query.all()), {'lamp_1', 'solo_1'})
        self.assertEqual(Value.query.count(), 2)
        self.assertEqual(History.query.count(), 2)

        self.assertEqual(Class.query.count(), 4)
        self.assertEqual(Property.query.filter(Property.name == 'root_prop').count(), 1)
        self.assertEqual(Property.query.filter(Property.name == 'other_prop').count(), 1)
        self.assertEqual(Method.query.filter(Method.name == 'other_method').count(), 1)
        self.assertEqual(Property.query.filter(Property.object_id == kept.id).count(), 1)
        self.assertEqual(Method.query.filter(Method.object_id == kept.id).count(), 1)


class TestCleanupOrphanRecords(ObjectDbSQLiteTestCase):
    def test_removes_orphan_object_rows(self):
        stale_prop = Property(name='orphan_prop', type='int', object_id=9999)
        stale_method = Method(name='orphan_method', object_id=9999, code='pass')
        stale_value = Value(object_id=9999, name='orphan_val', value='1')
        self.db.session.add_all([stale_prop, stale_method, stale_value])
        self.db.session.flush()
        self.db.session.add(History(value_id=stale_value.id, value='1'))
        self.db.session.commit()

        stats = cleanup_orphan_records()
        self.db.session.commit()

        self.assertEqual(stats['properties'], 1)
        self.assertEqual(stats['methods'], 1)
        self.assertEqual(stats['values'], 1)
        self.assertEqual(stats['history'], 1)
        self.assertEqual(Property.query.count(), 0)
        self.assertEqual(Method.query.count(), 0)
        self.assertEqual(Value.query.count(), 0)
        self.assertEqual(History.query.count(), 0)

    def test_removes_stale_class_properties_and_methods(self):
        cls = self._add_class('alive')
        self.db.session.add(Property(name='alive_prop', type='int', class_id=cls.id))
        self.db.session.add(Method(name='alive_method', class_id=cls.id, code='pass'))
        self.db.session.add(Property(name='dead_prop', type='int', class_id=8888))
        self.db.session.add(Method(name='dead_method', class_id=8888, code='pass'))
        self.db.session.commit()

        stats = cleanup_orphan_records()
        self.db.session.commit()

        self.assertEqual(stats['properties'], 1)
        self.assertEqual(stats['methods'], 1)
        self.assertEqual(Property.query.count(), 1)
        self.assertEqual(Method.query.count(), 1)
        self.assertEqual(Property.query.filter(Property.name == 'alive_prop').count(), 1)

    def test_keeps_valid_graph_when_mixed_with_orphans(self):
        cls = self._add_class('valid_cls')
        self.db.session.add(Property(name='class_prop', type='int', class_id=cls.id))
        self.db.session.add(Method(name='class_method', class_id=cls.id, code='pass'))
        valid = self._add_full_object('valid_obj', class_id=cls.id)
        self._add_value(valid.id, 'extra', '100', with_history=True)

        stale_prop = Property(name='orphan_prop', type='int', object_id=9999)
        stale_method = Method(name='orphan_method', object_id=9999, code='pass')
        stale_value = Value(object_id=9999, name='orphan_val', value='1')
        self.db.session.add_all([stale_prop, stale_method, stale_value])
        self.db.session.flush()
        self.db.session.add(History(value_id=stale_value.id, value='1'))
        self.db.session.add(Property(name='dead_class_prop', type='int', class_id=8888))
        self.db.session.commit()

        before = self._table_counts()
        stats = cleanup_orphan_records()
        self.db.session.commit()
        after = self._table_counts()

        self.assertEqual(stats['properties'], 2)
        self.assertEqual(stats['methods'], 1)
        self.assertEqual(stats['values'], 1)
        self.assertEqual(stats['history'], 1)

        self.assertEqual(after['objects'], before['objects'])
        self.assertEqual(after['classes'], before['classes'])
        self.assertEqual(after['objects'], 1)
        self.assertEqual(after['values'], 2)
        self.assertEqual(after['history'], 2)
        self.assertEqual(after['properties'], 2)
        self.assertEqual(after['methods'], 2)

        self.assertIsNotNone(Object.query.filter(Object.name == 'valid_obj').first())
        self.assertEqual(Property.query.filter(Property.name == 'class_prop').count(), 1)
        self.assertEqual(Property.query.filter(Property.object_id == valid.id).count(), 1)
        self.assertEqual(Value.query.filter(Value.object_id == valid.id).count(), 2)


class TestMigrateValuesForPropertyTypeChange(ObjectDbSQLiteTestCase):
    def test_returns_zero_when_types_equal(self):
        obj = self._add_full_object('meter')
        self.db.session.commit()

        updated = migrate_values_for_property_type_change(
            'temp', 'float', 'float', object_id=obj.id,
        )
        self.db.session.commit()

        self.assertEqual(updated, 0)
        val = Value.query.filter(Value.object_id == obj.id, Value.name == 'temp').one()
        self.assertEqual(val.value, '23.5')

    def test_updates_values_for_object_scope(self):
        obj = self._add_full_object('meter_obj')
        val = Value.query.filter(Value.object_id == obj.id, Value.name == 'temp').one()
        val.value = '42'
        self.db.session.commit()

        updated = migrate_values_for_property_type_change(
            'temp', 'int', 'float', object_id=obj.id,
        )
        self.db.session.commit()

        self.assertEqual(updated, 1)
        val = Value.query.filter(Value.object_id == obj.id, Value.name == 'temp').one()
        self.assertEqual(val.value, '42.0')

    def test_updates_values_for_class_scope(self):
        cls = self._add_class('meters')
        child = self._add_class('meters_child', parent_id=cls.id)
        obj_a = self._add_full_object('m_a', class_id=cls.id)
        obj_b = self._add_full_object('m_b', class_id=child.id)
        for obj in (obj_a, obj_b):
            val = Value.query.filter(Value.object_id == obj.id, Value.name == 'temp').one()
            val.value = '42'
        self.db.session.commit()

        updated = migrate_values_for_property_type_change(
            'temp', 'int', 'float', class_id=cls.id,
        )
        self.db.session.commit()

        self.assertEqual(updated, 2)
        for obj in (obj_a, obj_b):
            val = Value.query.filter(Value.object_id == obj.id, Value.name == 'temp').one()
            self.assertEqual(val.value, '42.0')

    def test_sets_none_for_invalid_conversion(self):
        obj = self._add_object('broken_val')
        self.db.session.add(Value(object_id=obj.id, name='count', value='broken'))
        self.db.session.commit()

        updated = migrate_values_for_property_type_change(
            'count', 'str', 'int', object_id=obj.id,
        )
        self.db.session.commit()

        self.assertEqual(updated, 1)
        val = Value.query.filter(Value.object_id == obj.id, Value.name == 'count').one()
        self.assertEqual(val.value, 'None')

    def test_migrates_only_target_property_and_object_scope(self):
        obj_a = self._add_full_object('meter_a')
        obj_b = self._add_full_object('meter_b')
        val_a_temp = Value.query.filter(Value.object_id == obj_a.id, Value.name == 'temp').one()
        val_a_temp.value = '42'
        val_b_temp = Value.query.filter(Value.object_id == obj_b.id, Value.name == 'temp').one()
        val_b_temp.value = '99'
        self._add_value(obj_a.id, 'pressure', '1000')
        self._add_value(obj_b.id, 'pressure', '2000')
        self.db.session.commit()

        updated = migrate_values_for_property_type_change(
            'temp', 'int', 'float', object_id=obj_a.id,
        )
        self.db.session.commit()

        self.assertEqual(updated, 1)
        self.assertEqual(
            Value.query.filter(Value.object_id == obj_a.id, Value.name == 'temp').one().value,
            '42.0',
        )
        self.assertEqual(
            Value.query.filter(Value.object_id == obj_a.id, Value.name == 'pressure').one().value,
            '1000',
        )
        self.assertEqual(
            Value.query.filter(Value.object_id == obj_b.id, Value.name == 'temp').one().value,
            '99',
        )
        self.assertEqual(
            Value.query.filter(Value.object_id == obj_b.id, Value.name == 'pressure').one().value,
            '2000',
        )

    def test_class_scope_does_not_touch_objects_outside_class_tree(self):
        in_tree = self._add_class('in_tree')
        outside = self._add_class('outside')
        obj_in = self._add_full_object('obj_in', class_id=in_tree.id)
        obj_out = self._add_full_object('obj_out', class_id=outside.id)
        for obj in (obj_in, obj_out):
            val = Value.query.filter(Value.object_id == obj.id, Value.name == 'temp').one()
            val.value = '42'
        self.db.session.commit()

        updated = migrate_values_for_property_type_change(
            'temp', 'int', 'float', class_id=in_tree.id,
        )
        self.db.session.commit()

        self.assertEqual(updated, 1)
        self.assertEqual(
            Value.query.filter(Value.object_id == obj_in.id, Value.name == 'temp').one().value,
            '42.0',
        )
        self.assertEqual(
            Value.query.filter(Value.object_id == obj_out.id, Value.name == 'temp').one().value,
            '42',
        )


class TestDeleteObjectApi(ObjectDbSQLiteTestCase):
    @patch('app.core.lib.object.objects_storage')
    @patch('app.core.lib.object_db.clearScheduledJob')
    def test_delete_object_removes_from_db_and_runtime(self, _mock_clear, mock_storage):
        from app.core.lib.object import deleteObject

        obj = self._add_full_object('to_delete')
        self.db.session.commit()

        result = deleteObject('to_delete')

        self.assertTrue(result)
        self.assertEqual(Object.query.count(), 0)
        self.assertEqual(Value.query.count(), 0)
        self.assertEqual(History.query.count(), 0)
        mock_storage.remove_object.assert_called_once_with('to_delete')

    @patch('app.core.lib.object.objects_storage')
    @patch('app.core.lib.object_db.clearScheduledJob')
    def test_keeps_other_object_when_deleting_one(self, _mock_clear, mock_storage):
        from app.core.lib.object import deleteObject

        self._add_full_object('to_delete')
        kept = self._add_full_object('to_keep')
        self._add_value(kept.id, 'extra', '77', with_history=True)
        self.db.session.commit()

        before = self._table_counts()

        result = deleteObject('to_delete')

        self.assertTrue(result)
        after = self._table_counts()
        self.assertEqual(after['objects'], before['objects'] - 1)
        self.assertEqual(after['values'], before['values'] - 1)
        self.assertEqual(after['history'], before['history'] - 1)
        self.assertEqual(after['properties'], before['properties'] - 1)
        self.assertEqual(after['methods'], before['methods'] - 1)

        self.assertIsNone(Object.query.filter(Object.name == 'to_delete').first())
        self.assertIsNotNone(Object.query.filter(Object.name == 'to_keep').first())
        self.assertEqual(Value.query.filter(Value.object_id == kept.id).count(), 2)
        mock_storage.remove_object.assert_called_once_with('to_delete')

    def test_delete_object_returns_false_when_missing(self):
        from app.core.lib.object import deleteObject

        self.assertFalse(deleteObject('missing'))


if __name__ == '__main__':
    unittest.main()
