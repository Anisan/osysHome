"""Tests for app.core.lib.object_tree (classes/objects structural cache)."""
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from app.core.models.Clasess import Class, Object
from app.core.lib import object_tree as ot
from app.core.lib.object_tree import (
    get_objects_tree_payload,
    invalidate_objects_tree_cache,
)


class ObjectTreeSQLiteTestCase(unittest.TestCase):
    """Flask + SQLite :memory: for each test; clear tree cache around tests."""

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
        invalidate_objects_tree_cache()

    def tearDown(self):
        invalidate_objects_tree_cache()
        self.db.session.remove()
        self.db.drop_all()
        self.ctx.pop()

    def _add_class(self, name, parent_id=None, description=''):
        cls = Class(name=name, description=description, parent_id=parent_id)
        self.db.session.add(cls)
        self.db.session.flush()
        return cls

    def _add_object(self, name, class_id=None, description=''):
        obj = Object(name=name, description=description, class_id=class_id)
        self.db.session.add(obj)
        self.db.session.flush()
        return obj


class TestBuildTreePayload(ObjectTreeSQLiteTestCase):
    def test_hierarchy_counts_and_standalone(self):
        root = self._add_class('Root', description='root class')
        child = self._add_class('Child', parent_id=root.id)
        self._add_object('Lamp', class_id=root.id)
        self._add_object('Sensor', class_id=child.id)
        self._add_object('Orphan')
        self.db.session.commit()

        payload = get_objects_tree_payload(include_hidden=False)

        self.assertEqual([c['name'] for c in payload['root_classes']], ['Root'])
        self.assertEqual(payload['root_classes'][0]['children_count'], 1)
        self.assertEqual(payload['root_classes'][0]['objects_count'], 1)

        children = payload['children_by_parent'][root.id]
        self.assertEqual([c['name'] for c in children], ['Child'])
        self.assertEqual(children[0]['objects_count'], 1)

        self.assertEqual(
            [o['name'] for o in payload['objects_by_class'][root.id]],
            ['Lamp'],
        )
        self.assertEqual(
            [o['name'] for o in payload['objects_by_class'][child.id]],
            ['Sensor'],
        )
        self.assertEqual(
            [o['name'] for o in payload['standalone_objects']],
            ['Orphan'],
        )
        self.assertIn(root.id, payload['classes_by_id'])
        self.assertEqual(payload['classes_by_id'][root.id]['description'], 'root class')

    def test_hides_underscore_prefixed_without_include_hidden(self):
        self._add_class('Visible')
        self._add_class('_Hidden')
        self._add_object('PublicObj')
        self._add_object('_SecretObj')
        self.db.session.commit()

        public = get_objects_tree_payload(include_hidden=False)
        self.assertEqual([c['name'] for c in public['root_classes']], ['Visible'])
        self.assertEqual([o['name'] for o in public['standalone_objects']], ['PublicObj'])

        all_payload = get_objects_tree_payload(include_hidden=True)
        names = sorted(c['name'] for c in all_payload['root_classes'])
        self.assertEqual(names, ['Visible', '_Hidden'])
        obj_names = sorted(o['name'] for o in all_payload['standalone_objects'])
        self.assertEqual(obj_names, ['PublicObj', '_SecretObj'])

    def test_sorts_by_name_case_insensitive(self):
        self._add_class('beta')
        self._add_class('Alpha')
        self._add_object('zebra')
        self._add_object('Apple')
        self.db.session.commit()

        payload = get_objects_tree_payload()
        self.assertEqual(
            [c['name'] for c in payload['root_classes']],
            ['Alpha', 'beta'],
        )
        self.assertEqual(
            [o['name'] for o in payload['standalone_objects']],
            ['Apple', 'zebra'],
        )


class TestTreeCacheLifecycle(ObjectTreeSQLiteTestCase):
    def test_caches_payload_and_invalidate_rebuilds(self):
        self._add_class('Only')
        self.db.session.commit()

        first = get_objects_tree_payload()
        self.assertEqual([c['name'] for c in first['root_classes']], ['Only'])
        self.assertIn('public', ot._TREE_CACHE)

        self._add_class('Second')
        self.db.session.commit()

        # Without invalidate — still stale cache
        stale = get_objects_tree_payload()
        self.assertEqual([c['name'] for c in stale['root_classes']], ['Only'])

        invalidate_objects_tree_cache()
        self.assertEqual(ot._TREE_CACHE, {})

        fresh = get_objects_tree_payload()
        self.assertEqual(
            [c['name'] for c in fresh['root_classes']],
            ['Only', 'Second'],
        )

    def test_public_and_all_are_separate_cache_keys(self):
        self._add_class('Visible')
        self._add_class('_Hidden')
        self.db.session.commit()

        get_objects_tree_payload(include_hidden=False)
        get_objects_tree_payload(include_hidden=True)

        self.assertIn('public', ot._TREE_CACHE)
        self.assertIn('all', ot._TREE_CACHE)
        public_names = [c['name'] for c in ot._TREE_CACHE['public']['root_classes']]
        all_names = sorted(c['name'] for c in ot._TREE_CACHE['all']['root_classes'])
        self.assertEqual(public_names, ['Visible'])
        self.assertEqual(all_names, ['Visible', '_Hidden'])

    def test_returned_payload_is_defensive_copy(self):
        self._add_class('Root')
        self.db.session.commit()

        payload = get_objects_tree_payload()
        payload['root_classes'][0]['name'] = 'Mutated'
        payload['root_classes'].append({'name': 'Extra'})

        again = get_objects_tree_payload()
        self.assertEqual([c['name'] for c in again['root_classes']], ['Root'])


class TestAddClassAppearsInTree(ObjectTreeSQLiteTestCase):
    """addClass must invalidate tree cache so the new class is visible immediately."""

    def _patch_session_scope(self):
        """Bind object.py session_scope to this test's Flask db.session."""

        @contextmanager
        def db_session_scope():
            yield self.db.session

        return patch('app.core.lib.object.session_scope', db_session_scope)

    @patch('app.core.lib.object.objects_storage')
    def test_add_class_appears_after_warm_cache(self, mock_storage):
        from app.core.lib.object import addClass

        # Warm empty cache (the stale-tree bug without invalidate)
        self.assertEqual(get_objects_tree_payload()['root_classes'], [])

        with self._patch_session_scope(), \
             patch('app.core.lib.object.row2dict', side_effect=lambda cls: {
                 'id': cls.id,
                 'name': cls.name,
                 'description': cls.description,
                 'parent_id': cls.parent_id,
             }):
            result = addClass('ApiClass', description='from API')

        self.assertEqual(result['name'], 'ApiClass')
        mock_storage.reload_objects_by_class.assert_called_once()

        payload = get_objects_tree_payload()
        self.assertEqual([c['name'] for c in payload['root_classes']], ['ApiClass'])
        self.assertEqual(payload['root_classes'][0]['description'], 'from API')
        self.assertEqual(payload['classes_by_id'][result['id']]['name'], 'ApiClass')

    @patch('app.core.lib.object.objects_storage')
    def test_add_child_class_under_parent(self, mock_storage):
        from app.core.lib.object import addClass

        parent = self._add_class('Parent')
        self.db.session.commit()
        get_objects_tree_payload()  # warm

        with self._patch_session_scope(), \
             patch('app.core.lib.object.row2dict', side_effect=lambda cls: {
                 'id': cls.id,
                 'name': cls.name,
                 'description': cls.description,
                 'parent_id': cls.parent_id,
             }):
            child = addClass('Child', parentId=parent.id)

        payload = get_objects_tree_payload()
        self.assertEqual([c['name'] for c in payload['root_classes']], ['Parent'])
        self.assertEqual(payload['root_classes'][0]['children_count'], 1)
        self.assertEqual(
            [c['name'] for c in payload['children_by_parent'][parent.id]],
            ['Child'],
        )
        self.assertEqual(payload['classes_by_id'][child['id']]['name'], 'Child')

    @patch('app.core.lib.object.objects_storage')
    def test_add_object_under_class_appears_in_tree(self, mock_storage):
        from app.core.lib.object import addObject

        cls = self._add_class('Devices')
        self.db.session.commit()
        get_objects_tree_payload()  # warm

        mock_storage.getObjectByName.return_value = MagicMock()

        with self._patch_session_scope():
            addObject('Lamp', class_name='Devices', description='living room')

        payload = get_objects_tree_payload()
        self.assertEqual(payload['classes_by_id'][cls.id]['objects_count'], 1)
        self.assertEqual(
            [o['name'] for o in payload['objects_by_class'][cls.id]],
            ['Lamp'],
        )


class TestCoreApiInvalidatesTreeCache(unittest.TestCase):
    """Structural mutations in object.py must clear the tree cache."""

    def test_add_class_invalidates(self):
        with patch('app.core.lib.object.session_scope') as scope, \
             patch('app.core.lib.object.objects_storage') as storage, \
             patch('app.core.lib.object.invalidate_objects_tree_cache') as inv, \
             patch('app.core.lib.object.row2dict', return_value={'name': 'X'}):
            session = MagicMock()
            scope.return_value.__enter__.return_value = session
            scope.return_value.__exit__.return_value = False
            session.query.return_value.filter.return_value.one_or_none.return_value = None

            from app.core.lib.object import addClass
            addClass('NewClass')

            inv.assert_called()
            storage.reload_objects_by_class.assert_called()

    def test_add_object_invalidates(self):
        with patch('app.core.lib.object.session_scope') as scope, \
             patch('app.core.lib.object.objects_storage') as storage, \
             patch('app.core.lib.object.invalidate_objects_tree_cache') as inv:
            session = MagicMock()
            scope.return_value.__enter__.return_value = session
            scope.return_value.__exit__.return_value = False
            session.query.return_value.filter.return_value.one_or_none.return_value = None
            storage.getObjectByName.return_value = MagicMock()

            from app.core.lib.object import addObject
            addObject('NewObj')

            inv.assert_called()
            storage.reload_object.assert_called()

    def test_delete_object_invalidates(self):
        with patch('app.core.lib.object.Object') as ObjectModel, \
             patch('app.core.lib.object.objects_storage') as storage, \
             patch('app.core.lib.object.invalidate_objects_tree_cache') as inv, \
             patch('app.database.db') as db, \
             patch('app.core.lib.object_db.delete_object_from_db', return_value='Gone'):
            ObjectModel.query.filter.return_value.one_or_none.return_value = MagicMock(id=1)

            from app.core.lib.object import deleteObject
            self.assertTrue(deleteObject('Gone'))

            inv.assert_called_once()
            storage.changeObject.assert_called_once_with('delete', 'Gone', None, None, None)
            storage.remove_object.assert_called_once_with('Gone')
            db.session.commit.assert_called()

    def test_rename_object_invalidates(self):
        with patch('app.core.lib.object.session_scope') as scope, \
             patch('app.core.lib.object.objects_storage') as storage, \
             patch('app.core.lib.object.invalidate_objects_tree_cache') as inv, \
             patch('app.core.lib.object.getProperty', return_value=None):
            session = MagicMock()
            scope.return_value.__enter__.return_value = session
            scope.return_value.__exit__.return_value = False
            obj = MagicMock(id=7)
            session.query.return_value.filter.return_value.one_or_none.side_effect = [
                obj,  # old name found
                None,  # new name free
            ]

            from app.core.lib.object import renameObject
            self.assertTrue(renameObject('Old', 'New'))

            inv.assert_called_once()
            storage.rename_object.assert_called_once_with('Old', 'New', 7)


if __name__ == '__main__':
    unittest.main()
