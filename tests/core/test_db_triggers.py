"""Тесты sync_model_triggers и protected_triggers (SQLite in-memory)."""
from __future__ import annotations

import json
import unittest

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.models.Clasess import Class, Method, Object, Property
from app.db_tools import DbTrigger, protected_triggers, sync_model_triggers


class DbTriggersSQLiteTestCase(unittest.TestCase):
    """Flask + SQLite :memory:."""

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
        sync_model_triggers(self.db.engine)

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.ctx.pop()

    def _trigger_names(self):
        rows = self.db.session.execute(
            text("SELECT name FROM sqlite_master WHERE type='trigger'")
        ).fetchall()
        return {r[0] for r in rows}

    def test_protected_triggers_have_all_dialect_bodies(self):
        triggers = protected_triggers(immutable_columns=("name",))
        self.assertGreaterEqual(len(triggers), 2)
        for trg in triggers:
            self.assertTrue(
                {"sqlite", "postgresql", "mysql"} <= set(trg.body.keys()),
                msg=trg.name,
            )

    def test_sync_creates_protected_triggers(self):
        names = self._trigger_names()
        for table in ("classes", "objects", "properties", "methods"):
            self.assertIn(f"trg_{table}_protected_upd", names)
            self.assertIn(f"trg_{table}_protected_del", names)

    def test_sync_idempotent(self):
        sync_model_triggers(self.db.engine)
        sync_model_triggers(self.db.engine)
        self.assertIn("trg_objects_protected_upd", self._trigger_names())

    def test_protected_object_blocks_name_and_class_change(self):
        cls = Class(name="ClsA", description="")
        self.db.session.add(cls)
        self.db.session.flush()
        obj = Object(
            name="Lamp",
            description="d",
            class_id=cls.id,
            params=json.dumps({"protected": True}),
        )
        self.db.session.add(obj)
        self.db.session.commit()

        obj.name = "Lamp2"
        with self.assertRaises((IntegrityError, OperationalError)):
            self.db.session.commit()
        self.db.session.rollback()

        obj = Object.query.filter_by(name="Lamp").one()
        obj.class_id = None
        with self.assertRaises((IntegrityError, OperationalError)):
            self.db.session.commit()
        self.db.session.rollback()

    def test_protected_object_allows_description_and_extra_params(self):
        obj = Object(
            name="Sensor",
            description="old",
            params=json.dumps({"protected": True}),
        )
        self.db.session.add(obj)
        self.db.session.commit()

        obj.description = "new"
        obj.params = json.dumps({"protected": True, "icon": "thermometer"})
        self.db.session.commit()

        obj = Object.query.filter_by(name="Sensor").one()
        self.assertEqual(obj.description, "new")
        self.assertEqual(json.loads(obj.params)["icon"], "thermometer")

    def test_protected_object_blocks_clearing_flag(self):
        obj = Object(
            name="Locked",
            description="",
            params=json.dumps({"protected": True}),
        )
        self.db.session.add(obj)
        self.db.session.commit()

        obj.params = json.dumps({"icon": "x"})
        with self.assertRaises((IntegrityError, OperationalError)):
            self.db.session.commit()
        self.db.session.rollback()

    def test_protected_object_blocks_delete(self):
        obj = Object(
            name="KeepMe",
            description="",
            params=json.dumps({"protected": True}),
        )
        self.db.session.add(obj)
        self.db.session.commit()

        self.db.session.delete(obj)
        with self.assertRaises((IntegrityError, OperationalError)):
            self.db.session.commit()
        self.db.session.rollback()
        self.assertIsNotNone(Object.query.filter_by(name="KeepMe").one_or_none())

    def test_unprotected_object_can_be_deleted(self):
        obj = Object(name="Temp", description="", params=None)
        self.db.session.add(obj)
        self.db.session.commit()
        self.db.session.delete(obj)
        self.db.session.commit()
        self.assertIsNone(Object.query.filter_by(name="Temp").one_or_none())

    def test_protected_class_blocks_parent_change(self):
        parent = Class(name="Parent", description="")
        child = Class(
            name="Child",
            description="",
            parent_id=None,
            params=json.dumps({"protected": True}),
        )
        self.db.session.add_all([parent, child])
        self.db.session.commit()

        child = Class.query.filter_by(name="Child").one()
        child.parent_id = parent.id
        with self.assertRaises((IntegrityError, OperationalError)):
            self.db.session.commit()
        self.db.session.rollback()

    def test_protected_property_blocks_type_change(self):
        obj = Object(name="Dev", description="")
        self.db.session.add(obj)
        self.db.session.flush()
        prop = Property(
            name="temp",
            object_id=obj.id,
            type="float",
            params=json.dumps({"protected": True}),
        )
        self.db.session.add(prop)
        self.db.session.commit()

        prop.type = "int"
        with self.assertRaises((IntegrityError, OperationalError)):
            self.db.session.commit()
        self.db.session.rollback()

    def test_protected_method_blocks_name_change(self):
        obj = Object(name="Dev2", description="")
        self.db.session.add(obj)
        self.db.session.flush()
        method = Method(
            name="run",
            object_id=obj.id,
            code="pass",
            params=json.dumps({"protected": True}),
        )
        self.db.session.add(method)
        self.db.session.commit()

        method.name = "run2"
        with self.assertRaises((IntegrityError, OperationalError)):
            self.db.session.commit()
        self.db.session.rollback()

    def test_raw_db_trigger(self):
        """Произвольный DbTrigger ставится и срабатывает."""
        from app.database import Column, SurrogatePK, db

        class TriggerProbe(SurrogatePK, db.Model):
            __tablename__ = "trigger_probe"
            __db_triggers__ = (
                DbTrigger(
                    name="block_name",
                    timing="BEFORE",
                    event="UPDATE",
                    body={
                        "sqlite": (
                            "SELECT CASE WHEN NEW.name IS NOT OLD.name THEN "
                            "RAISE(ABORT, 'probe: name locked') END;"
                        ),
                    },
                ),
            )
            name = Column(db.String(50))
            note = Column(db.String(50))

        TriggerProbe.__table__.create(self.db.engine)
        sync_model_triggers(self.db.engine)
        self.assertIn("trg_trigger_probe_block_name", self._trigger_names())

        row = TriggerProbe(name="a", note="1")
        self.db.session.add(row)
        self.db.session.commit()

        row.note = "2"
        self.db.session.commit()

        row.name = "b"
        with self.assertRaises((IntegrityError, OperationalError)):
            self.db.session.commit()
        self.db.session.rollback()


if __name__ == "__main__":
    unittest.main()
