"""Tests that object.py delete APIs emit changeObject with correct args."""

import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, call, patch

from app.core.models.Clasess import Class, Method, Object, Property, Value


class ChangeObjectNotifySQLiteTestCase(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        from app.extensions import db

        self.app = Flask(__name__)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(self.app)
        self.db = db
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.db.create_all()

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.ctx.pop()

    def _patch_session_scope(self):
        @contextmanager
        def db_session_scope():
            yield self.db.session

        return patch("app.core.lib.object.session_scope", db_session_scope)

    def _add_class(self, name):
        cls = Class(name=name, description="")
        self.db.session.add(cls)
        self.db.session.flush()
        return cls

    def _add_object(self, name, class_id=None):
        obj = Object(name=name, description="", class_id=class_id)
        self.db.session.add(obj)
        self.db.session.flush()
        return obj


class TestDeleteObjectNotify(unittest.TestCase):
    def test_delete_object_emits_change_object_before_remove(self):
        with patch("app.core.lib.object.Object") as ObjectModel, \
             patch("app.core.lib.object.objects_storage") as storage, \
             patch("app.core.lib.object.invalidate_objects_tree_cache"), \
             patch("app.database.db") as db, \
             patch("app.core.lib.object_db.delete_object_from_db", return_value="Alice"):
            ObjectModel.query.filter.return_value.one_or_none.return_value = MagicMock(id=1)

            from app.core.lib.object import deleteObject
            self.assertTrue(deleteObject("Alice"))

            storage.changeObject.assert_called_once_with("delete", "Alice", None, None, None)
            storage.remove_object.assert_called_once_with("Alice")
            change_idx = [
                i for i, c in enumerate(storage.mock_calls) if c[0] == "changeObject"
            ][0]
            remove_idx = [
                i for i, c in enumerate(storage.mock_calls) if c[0] == "remove_object"
            ][0]
            self.assertLess(change_idx, remove_idx)
            db.session.commit.assert_called()

    def test_delete_object_missing_skips_notify(self):
        with patch("app.core.lib.object.Object") as ObjectModel, \
             patch("app.core.lib.object.objects_storage") as storage:
            ObjectModel.query.filter.return_value.one_or_none.return_value = None

            from app.core.lib.object import deleteObject
            self.assertFalse(deleteObject("Missing"))

            storage.changeObject.assert_not_called()
            storage.remove_object.assert_not_called()


class TestDeletePropertyMethodNotify(ChangeObjectNotifySQLiteTestCase):
    @patch("app.core.lib.object.objects_storage")
    def test_delete_object_property_emits_change_object(self, storage):
        obj = self._add_object("Alice")
        self.db.session.add(Property(name="temp", type="float", object_id=obj.id))
        self.db.session.add(Value(object_id=obj.id, name="temp", value="1"))
        self.db.session.commit()

        from app.core.lib.object import deleteObjectProperty

        with self._patch_session_scope():
            self.assertTrue(deleteObjectProperty("Alice.temp"))

        storage.changeObject.assert_called_once_with("delete", "Alice", "temp", None, None)
        storage.reload_object.assert_called_once_with(obj.id)
        self.assertIsNone(
            Property.query.filter(Property.object_id == obj.id, Property.name == "temp").one_or_none()
        )

    @patch("app.core.lib.object.objects_storage")
    def test_delete_object_method_emits_change_object(self, storage):
        obj = self._add_object("Alice")
        self.db.session.add(Method(name="ping", object_id=obj.id, code="pass"))
        self.db.session.commit()

        from app.core.lib.object import deleteObjectMethod

        with self._patch_session_scope():
            self.assertTrue(deleteObjectMethod("Alice.ping"))

        storage.changeObject.assert_called_once_with("delete", "Alice", None, "ping", None)
        storage.reload_object.assert_called_once_with(obj.id)

    @patch("app.core.lib.object.objects_storage")
    def test_delete_class_property_notifies_each_object(self, storage):
        cls = self._add_class("Users")
        alice = self._add_object("Alice", class_id=cls.id)
        bob = self._add_object("Bob", class_id=cls.id)
        self.db.session.add(Property(name="home", type="bool", class_id=cls.id))
        self.db.session.commit()

        from app.core.lib.object import deleteClassProperty

        with self._patch_session_scope():
            self.assertTrue(deleteClassProperty("Users.home"))

        storage.changeObject.assert_has_calls(
            [
                call("delete", "Alice", "home", None, None),
                call("delete", "Bob", "home", None, None),
            ],
            any_order=True,
        )
        self.assertEqual(storage.changeObject.call_count, 2)
        storage.reload_objects_by_class.assert_called_once_with(cls.id)
        self.assertIsNotNone(alice.id)
        self.assertIsNotNone(bob.id)

    @patch("app.core.lib.object.objects_storage")
    def test_delete_class_method_notifies_each_object(self, storage):
        cls = self._add_class("Users")
        self._add_object("Alice", class_id=cls.id)
        self._add_object("Bob", class_id=cls.id)
        self.db.session.add(Method(name="arrive", class_id=cls.id, code="pass"))
        self.db.session.commit()

        from app.core.lib.object import deleteClassMethod

        with self._patch_session_scope():
            self.assertTrue(deleteClassMethod("Users.arrive"))

        storage.changeObject.assert_has_calls(
            [
                call("delete", "Alice", None, "arrive", None),
                call("delete", "Bob", None, "arrive", None),
            ],
            any_order=True,
        )
        self.assertEqual(storage.changeObject.call_count, 2)
        storage.reload_objects_by_class.assert_called_once_with(cls.id)


if __name__ == "__main__":
    unittest.main()
