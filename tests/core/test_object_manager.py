"""
Тесты для app.core.main.ObjectManager

Покрывает следующие классы:
- ValueUpdate (dataclass)
- BatchWriter
- PropertyManager
- MethodManager
- ObjectManager
"""
import unittest
from unittest.mock import Mock, patch, MagicMock, PropertyMock
import datetime
import json
import time
import threading
from dataclasses import dataclass

# Импорты из приложения
from app.core.main.ObjectManager import (
    ValueUpdate,
    BatchWriter,
    PropertyManager,
    MethodManager,
    ObjectManager,
    TypeOperation
)
from app.core.models.Clasess import Object, Property, Value, History


class TestValueUpdate(unittest.TestCase):
    """Тесты для dataclass ValueUpdate"""
    
    def test_value_update_creation(self):
        """Тест создания ValueUpdate"""
        now = datetime.datetime.now()
        update = ValueUpdate(
            value_id=1,
            value="test_value",
            changed=now,
            source="test_source",
            save_history=True,
            history_value="history_value"
        )
        
        self.assertEqual(update.value_id, 1)
        self.assertEqual(update.value, "test_value")
        self.assertEqual(update.changed, now)
        self.assertEqual(update.source, "test_source")
        self.assertTrue(update.save_history)
        self.assertEqual(update.history_value, "history_value")
    
    def test_value_update_optional_history(self):
        """Тест ValueUpdate с опциональным history_value"""
        now = datetime.datetime.now()
        update = ValueUpdate(
            value_id=1,
            value="test_value",
            changed=now,
            source="test_source",
            save_history=False
        )
        
        self.assertIsNone(update.history_value)


class TestBatchWriter(unittest.TestCase):
    """Тесты для BatchWriter"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        # Не писать в реальную БД (value_id=1 = SystemVar.Started в app.db)
        self._session_scope_patcher = patch('app.core.main.ObjectManager.session_scope')
        mock_session_scope = self._session_scope_patcher.start()
        mock_db_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = mock_db_session
        mock_ctx.__exit__.return_value = None
        mock_session_scope.return_value = mock_ctx
        self.mock_db_session = mock_db_session
        self.batch_writer = BatchWriter(flush_interval=0.1)
    
    def tearDown(self):
        """Очистка после каждого теста"""
        self.batch_writer.shutdown(wait=True)
        self._session_scope_patcher.stop()
        time.sleep(0.2)  # Даем время на завершение потоков
    
    def test_batch_writer_initialization(self):
        """Тест инициализации BatchWriter"""
        self.assertIsNotNone(self.batch_writer._lock)
        self.assertEqual(len(self.batch_writer._batch), 0)
        self.assertIsNotNone(self.batch_writer._worker_thread)
        self.assertTrue(self.batch_writer._worker_thread.is_alive())
    
    def test_add_value_update(self):
        """Тест добавления ValueUpdate в батч"""
        now = datetime.datetime.now()
        update = ValueUpdate(
            value_id=1,
            value="test",
            changed=now,
            source="test",
            save_history=False
        )
        
        initial_total = self.batch_writer._total_added
        self.batch_writer.add(update)
        
        self.assertEqual(len(self.batch_writer._batch), 1)
        self.assertEqual(self.batch_writer._total_added, initial_total + 1)
    
    def test_flush(self):
        """Тест принудительной записи батча"""
        now = datetime.datetime.now()
        update = ValueUpdate(
            value_id=1,
            value="test",
            changed=now,
            source="test",
            save_history=False
        )
        
        self.batch_writer.add(update)
        self.batch_writer.flush()
        
        # Даем время на выполнение
        time.sleep(0.2)
        
        # Батч должен быть очищен после flush
        self.assertEqual(len(self.batch_writer._batch), 0)
    
    def test_get_stats(self):
        """Тест получения статистики"""
        stats = self.batch_writer.get_stats()
        
        self.assertIn("flush_interval", stats)
        self.assertIn("current_batch_size", stats)
        self.assertIn("total_added", stats)
        self.assertIn("total_flushed", stats)
        self.assertIn("total_values_updated", stats)
        self.assertIn("total_history_inserted", stats)
        self.assertIn("total_errors", stats)
        self.assertIn("execution_time", stats)
        self.assertIn("flush_history", stats)
        self.assertIsInstance(stats["flush_history"], list)
        self.assertIn("efficiency", stats)

    def test_empty_flush_recorded_in_history(self):
        """Пустой flush тоже попадает в историю для графика"""
        initial_flushed = self.batch_writer.get_stats()["total_flushed"]
        self.batch_writer._flush_internal()
        stats = self.batch_writer.get_stats()

        self.assertEqual(len(stats["flush_history"]), 1)
        entry = stats["flush_history"][0]
        self.assertEqual(entry["batch_size"], 0)
        self.assertEqual(entry["values_count"], 0)
        self.assertEqual(entry["history_count"], 0)
        self.assertTrue(entry["success"])
        self.assertEqual(stats["total_flushed"], initial_flushed)


class TestPropertyManager(unittest.TestCase):
    """Тесты для PropertyManager"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        # Создаем моки для Property и Value
        self.mock_property = Mock()
        self.mock_property.id = 1
        self.mock_property.name = "test_property"
        self.mock_property.description = "Test Property"
        self.mock_property.history = 0
        self.mock_property.type = "str"
        self.mock_property.params = None
        
        self.mock_value = Mock()
        self.mock_value.id = 1
        self.mock_value.value = "test_value"
        self.mock_value.changed = datetime.datetime.now()
        self.mock_value.source = "test_source"
        self.mock_value.linked = None
        
        self.object_id = 1
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_property_manager_init_with_value(self, mock_now):
        """Тест инициализации PropertyManager с значением"""
        mock_now.return_value = datetime.datetime.now()
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, self.mock_value)
        
        self.assertEqual(prop_manager.property_id, 1)
        self.assertEqual(prop_manager.value_id, 1)
        self.assertEqual(prop_manager.name, "test_property")
        self.assertEqual(prop_manager.object_id, self.object_id)
        self.assertEqual(prop_manager.value, "test_value")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_property_manager_init_without_value(self, mock_now):
        """Тест инициализации PropertyManager без значения"""
        mock_now.return_value = datetime.datetime.now()
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        self.assertEqual(prop_manager.value_id, None)
        self.assertIsNone(prop_manager.value)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_property_manager_params_parsing(self, mock_now):
        """Тест парсинга параметров из JSON"""
        mock_now.return_value = datetime.datetime.now()
        
        params = {
            "icon": "fa-icon",
            "color": "#FF0000",
            "sort_order": 1,
            "default_value": "default",
            "read_only": True,
            "min": 0,
            "max": 100
        }
        self.mock_property.params = json.dumps(params)
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        self.assertEqual(prop_manager.icon, "fa-icon")
        self.assertEqual(prop_manager.color, "#FF0000")
        self.assertEqual(prop_manager.sort_order, 1)
        self.assertEqual(prop_manager.default_value, "default")
        self.assertTrue(prop_manager.read_only)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_decode_value_int(self, mock_now):
        """Тест декодирования значения типа int"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.type = "int"
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        self.assertEqual(prop_manager._decodeValue("42"), 42)
        self.assertEqual(prop_manager._decodeValue("0"), 0)
        self.assertIsNone(prop_manager._decodeValue(""))
        self.assertIsNone(prop_manager._decodeValue(None))
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_decode_value_int_with_constraints(self, mock_now):
        """Тест декодирования int с ограничениями min/max"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.type = "int"
        self.mock_property.params = json.dumps({"min": 0, "max": 100})
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        # Валидные значения
        self.assertEqual(prop_manager._decodeValue("50"), 50)
        self.assertEqual(prop_manager._decodeValue("0"), 0)
        self.assertEqual(prop_manager._decodeValue("100"), 100)
        
        # Невалидные значения должны выбрасывать ValueError
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("-1")
        
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("101")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_decode_value_float(self, mock_now):
        """Тест декодирования значения типа float"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.type = "float"
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        self.assertEqual(prop_manager._decodeValue("3.14"), 3.14)
        self.assertEqual(prop_manager._decodeValue("0.0"), 0.0)
        self.assertIsNone(prop_manager._decodeValue(""))
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_decode_value_float_with_decimals(self, mock_now):
        """Тест округления float до указанного количества знаков"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.type = "float"
        self.mock_property.params = json.dumps({"decimals": 2})
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        self.assertEqual(prop_manager._decodeValue("3.14159"), 3.14)
        self.assertEqual(prop_manager._decodeValue("2.999"), 3.0)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_decode_value_float_with_constraints(self, mock_now):
        """Тест декодирования float с ограничениями min/max"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.type = "float"
        self.mock_property.params = json.dumps({"min": 0.0, "max": 100.0})
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        # Валидные значения
        self.assertEqual(prop_manager._decodeValue("50.5"), 50.5)
        
        # Невалидные значения
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("-0.1")
        
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("100.1")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_decode_value_str_with_regexp(self, mock_now):
        """Тест декодирования строки с регулярным выражением"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.type = "str"
        self.mock_property.params = json.dumps({"regexp": "^[A-Z]{3}-\\d{4}$"})
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        # Валидное значение
        self.assertEqual(prop_manager._decodeValue("ABC-1234"), "ABC-1234")
        
        # Невалидное значение
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("abc-1234")
        
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("ABC-12")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_decode_value_bool(self, mock_now):
        """Тест декодирования значения типа bool"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.type = "bool"
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        # Различные варианты True
        self.assertTrue(prop_manager._decodeValue("true"))
        self.assertTrue(prop_manager._decodeValue("True"))
        self.assertTrue(prop_manager._decodeValue("1"))
        self.assertTrue(prop_manager._decodeValue("yes"))
        self.assertTrue(prop_manager._decodeValue("on"))
        
        # Различные варианты False
        self.assertFalse(prop_manager._decodeValue("false"))
        self.assertFalse(prop_manager._decodeValue("False"))
        self.assertFalse(prop_manager._decodeValue("0"))
        self.assertFalse(prop_manager._decodeValue("no"))
        self.assertFalse(prop_manager._decodeValue("off"))
        
        # Невалидное значение
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("invalid")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_decode_value_enum(self, mock_now):
        """Тест декодирования значения типа enum"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.type = "enum"
        enum_values = {"0": "Off", "1": "On", "2": "Auto"}
        self.mock_property.params = json.dumps({"enum_values": enum_values})
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        # Валидные значения
        self.assertEqual(prop_manager._decodeValue("0"), "0")
        self.assertEqual(prop_manager._decodeValue("1"), "1")
        self.assertEqual(prop_manager._decodeValue("2"), "2")
        
        # Невалидное значение
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("3")

    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_decode_value_color(self, mock_now):
        """Тест декодирования значения типа color"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.type = "color"
        self.mock_property.params = json.dumps({
            "read_format": "canonical",
            "write_format": "auto"
        })
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)

        value = prop_manager._decodeValue("#547CFF", init=False)
        self.assertIsInstance(value, dict)
        self.assertIn("rgb", value)
        self.assertIn("xy", value)

    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_color_read_format_hex(self, mock_now):
        """Тест выдачи значения color в read_format=hex"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.type = "color"
        self.mock_property.params = json.dumps({
            "read_format": "hex",
            "write_format": "auto",
        })
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        prop_manager.setValue("#547CFF")
        value = prop_manager.getValue()
        self.assertTrue(isinstance(value, str) and value.startswith("#"))

    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_color_format_output_value_xy(self, mock_now):
        """Тест форматирования color для выдачи в read_format=xy"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.type = "color"
        self.mock_property.params = json.dumps({
            "read_format": "xy",
            "write_format": "auto",
        })
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        prop_manager.setValue("#547CFF")
        value = prop_manager._format_output_value(prop_manager._decodeValue("#547CFF", init=True))
        self.assertIsInstance(value, dict)
        self.assertIn("x", value)
        self.assertIn("y", value)
        self.assertNotIn("rgb", value)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_decode_value_dict(self, mock_now):
        """Тест декодирования значения типа dict"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.type = "dict"
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        test_dict = {"key": "value", "number": 42}
        json_str = json.dumps(test_dict)
        
        result = prop_manager._decodeValue(json_str)
        self.assertEqual(result, test_dict)
        
        # Прямая передача dict
        result2 = prop_manager._decodeValue(test_dict)
        self.assertEqual(result2, test_dict)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_decode_value_list(self, mock_now):
        """Тест декодирования значения типа list"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.type = "list"
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        test_list = [1, 2, 3, "test"]
        json_str = json.dumps(test_list)
        
        result = prop_manager._decodeValue(json_str)
        self.assertEqual(result, test_list)
        
        # Прямая передача list
        result2 = prop_manager._decodeValue(test_list)
        self.assertEqual(result2, test_list)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    def test_set_value_read_only(self, mock_user, mock_now):
        """Тест установки значения в read-only свойство"""
        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None
        
        self.mock_property.params = json.dumps({"read_only": True})
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        with self.assertRaises(PermissionError):
            prop_manager.setValue("new_value")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager._batch_writer')
    def test_set_value(self, mock_batch_writer, mock_user, mock_now):
        """Тест установки значения"""
        now = datetime.datetime.now()
        mock_now.return_value = now
        mock_user.username = None
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        prop_manager.value_id = 1  # Устанавливаем value_id для сохранения
        
        prop_manager.setValue("new_value", source="test")
        
        self.assertEqual(prop_manager.value, "new_value")
        self.assertEqual(prop_manager.source, "test")
        self.assertEqual(prop_manager.changed, now)
        self.assertEqual(prop_manager.count_write, 1)
        self.assertGreaterEqual(mock_batch_writer.add.call_count, 1)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_get_value(self, mock_now):
        """Тест получения значения"""
        mock_now.return_value = datetime.datetime.now()
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, self.mock_value)
        
        value = prop_manager.getValue()
        self.assertEqual(value, "test_value")
        self.assertEqual(prop_manager.count_read, 1)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_get_value_with_default(self, mock_now):
        """Тест получения значения по умолчанию"""
        mock_now.return_value = datetime.datetime.now()
        self.mock_property.params = json.dumps({"default_value": "default"})
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        
        # Если value_id None и __value None, должен вернуться default_value
        value = prop_manager.getValue()
        self.assertEqual(value, "default")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_encode_value(self, mock_now):
        """Тест кодирования значения в строку"""
        mock_now.return_value = datetime.datetime.now()
        
        # Тест int
        self.mock_property.type = "int"
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        prop_manager.value = 42
        self.assertEqual(prop_manager._encodeValue(), "42")
        
        # Тест float
        self.mock_property.type = "float"
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        prop_manager.value = 3.14
        self.assertEqual(prop_manager._encodeValue(), "3.14")
        
        # Тест str
        self.mock_property.type = "str"
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        prop_manager.value = "test"
        self.assertEqual(prop_manager._encodeValue(), "test")
        
        # Тест None
        prop_manager.value = None
        self.assertEqual(prop_manager._encodeValue(), "None")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_property_value_property(self, mock_now):
        """Тест property value (getter/setter)"""
        mock_now.return_value = datetime.datetime.now()
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, None)
        prop_manager.value_id = 1
        
        # Getter
        prop_manager.value = "test"
        self.assertEqual(prop_manager.value, "test")
        
        # Setter
        with patch.object(prop_manager, 'setValue') as mock_set:
            prop_manager.value = "new_value"
            mock_set.assert_called_once_with("new_value")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.convert_utc_to_local')
    def test_to_dict(self, mock_convert, mock_now):
        """Тест преобразования в словарь"""
        now = datetime.datetime.now()
        mock_now.return_value = now
        mock_convert.return_value = now
        
        prop_manager = PropertyManager(self.object_id, self.mock_property, self.mock_value)
        prop_manager.value = "test_value"
        
        result = prop_manager.to_dict()
        
        self.assertEqual(result["property_id"], 1)
        self.assertEqual(result["value_id"], 1)
        self.assertEqual(result["name"], "test_property")
        self.assertEqual(result["type"], "str")
        self.assertEqual(result["value"], "test_value")
        self.assertEqual(result["count_read"], 1)
        self.assertEqual(result["count_write"], 1)


class TestMethodManager(unittest.TestCase):
    """Тесты для MethodManager"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.methods = [
            {
                "name": "test_method",
                "description": "Test Method",
                "code": "return 'test'",
                "owner": "test_owner"
            }
        ]
    
    def test_method_manager_init(self):
        """Тест инициализации MethodManager"""
        method_manager = MethodManager(self.methods)
        
        self.assertEqual(method_manager.name, "test_method")
        self.assertEqual(method_manager.description, "Test Method")
        self.assertEqual(method_manager.methods, self.methods)
        self.assertEqual(method_manager.count_executed, 0)
        self.assertIsNone(method_manager.executed)
        self.assertIsNone(method_manager.source)
    
    @patch('app.core.main.ObjectManager.convert_utc_to_local')
    def test_to_dict(self, mock_convert):
        """Тест преобразования в словарь"""
        now = datetime.datetime.now()
        mock_convert.return_value = now
        
        method_manager = MethodManager(self.methods)
        method_manager.executed = datetime.datetime.now()
        method_manager.exec_params = {"param": "value"}
        method_manager.exec_result = "result"
        method_manager.exec_time = 100
        method_manager.source = "test_source"
        
        result = method_manager.to_dict()
        
        self.assertEqual(result["name"], "test_method")
        self.assertEqual(result["description"], "Test Method")
        self.assertEqual(result["methods"], self.methods)
        self.assertEqual(result["count_executed"], 0)
        self.assertEqual(result["exec_params"], {"param": "value"})
        self.assertEqual(result["exec_result"], "result")
        self.assertEqual(result["exec_time"], 100)
        self.assertEqual(result["source"], "test_source")


class TestObjectManager(unittest.TestCase):
    """Тесты для ObjectManager"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.mock_object = Mock()
        self.mock_object.id = 1
        self.mock_object.name = "test_object"
        self.mock_object.description = "Test Object"
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_object_manager_init(self, mock_now):
        """Тест инициализации ObjectManager"""
        mock_now.return_value = datetime.datetime.now()
        
        obj_manager = ObjectManager(self.mock_object)
        
        self.assertEqual(obj_manager.object_id, 1)
        self.assertEqual(obj_manager.name, "test_object")
        self.assertEqual(obj_manager.description, "Test Object")
        self.assertEqual(len(obj_manager.properties), 0)
        self.assertEqual(len(obj_manager.methods), 0)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager.session_scope')
    @patch('app.core.main.ObjectManager._batch_writer')
    def test_set_property(self, mock_batch_writer, mock_session, mock_user, mock_now):
        """Тест установки свойства"""
        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None
        
        # Мокируем сессию БД
        mock_session.return_value.__enter__.return_value = MagicMock()
        mock_session.return_value.__exit__.return_value = None
        
        obj_manager = ObjectManager(self.mock_object)
        
        # Создаем мок для Property
        mock_prop_db = Mock()
        mock_prop_db.id = 1
        mock_prop_db.name = "test_prop"
        mock_prop_db.description = ""
        mock_prop_db.history = 0
        mock_prop_db.type = "str"
        mock_prop_db.params = None
        
        with patch('app.core.main.ObjectManager.Property', return_value=mock_prop_db):
            result = obj_manager.setProperty("test_prop", "test_value", source="test")
        
        self.assertTrue(result)
        self.assertIn("test_prop", obj_manager.properties)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    def test_set_property_validation_error(self, mock_user, mock_now):
        """Тест установки свойства с ошибкой валидации"""
        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None
        
        obj_manager = ObjectManager(self.mock_object)
        
        # Создаем свойство с ограничениями
        mock_prop = Mock()
        mock_prop.id = 1
        mock_prop.name = "test_prop"
        mock_prop.description = ""
        mock_prop.history = 0
        mock_prop.type = "int"
        mock_prop.params = json.dumps({"min": 0, "max": 100})
        
        mock_value = Mock()
        mock_value.id = 1
        mock_value.value = "50"
        mock_value.changed = datetime.datetime.now()
        mock_value.source = "test"
        mock_value.linked = None
        
        prop_manager = PropertyManager(1, mock_prop, mock_value)
        obj_manager.properties["test_prop"] = prop_manager
        
        # Попытка установить невалидное значение
        with self.assertRaises(ValueError) as context:
            obj_manager.setProperty("test_prop", "150", source="test")
        
        self.assertIn("greater than maximum ", str(context.exception))
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    def test_get_property(self, mock_user, mock_now):
        """Тест получения свойства"""
        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None
        
        obj_manager = ObjectManager(self.mock_object)
        
        # Создаем свойство
        mock_prop = Mock()
        mock_prop.id = 1
        mock_prop.name = "test_prop"
        mock_prop.description = ""
        mock_prop.history = 0
        mock_prop.type = "str"
        mock_prop.params = None
        
        mock_value = Mock()
        mock_value.id = 1
        mock_value.value = "test_value"
        mock_value.changed = datetime.datetime.now()
        mock_value.source = "test"
        mock_value.linked = None
        
        prop_manager = PropertyManager(1, mock_prop, mock_value)
        obj_manager.properties["test_prop"] = prop_manager
        
        value = obj_manager.getProperty("test_prop")
        self.assertEqual(value, "test_value")

    @patch('app.core.lib.common.is_datetime_in_range', return_value=False)
    @patch('app.core.main.ObjectManager.convert_utc_to_local', side_effect=lambda x: x)
    @patch('app.core.main.ObjectManager.convert_local_to_utc', side_effect=lambda x: x)
    @patch('app.core.main.ObjectManager.session_scope')
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    def test_color_history_uses_read_format(
        self, mock_user, mock_now, mock_session, mock_convert_local, mock_convert_utc, mock_in_range
    ):
        """История color возвращает значения в read_format, а не canonical"""
        from app.core.lib.converters.color_value import encode

        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None
        mock_session.return_value.__enter__.return_value = MagicMock()
        mock_session.return_value.__exit__.return_value = None

        obj_manager = ObjectManager(self.mock_object)

        mock_prop = Mock()
        mock_prop.id = 1
        mock_prop.name = "color_prop"
        mock_prop.description = ""
        mock_prop.history = 30
        mock_prop.type = "color"
        mock_prop.params = json.dumps({
            "read_format": "hex",
            "write_format": "auto",
        })

        mock_value = Mock()
        mock_value.id = 1
        mock_value.value = encode({"rgb": [84, 124, 255], "xy": [0.192685, 0.156741], "Y": 23.52})
        mock_value.changed = datetime.datetime.now()
        mock_value.source = "test"
        mock_value.linked = None

        prop_manager = PropertyManager(1, mock_prop, mock_value)
        prop_manager.value_id = 1
        obj_manager.properties["color_prop"] = prop_manager

        stored = encode({"rgb": [255, 0, 0], "xy": [0.640074, 0.329971], "Y": 21.26})
        with patch(
            'app.core.main.ObjectManager.History.getHistory',
            return_value=[{"value": stored, "added": datetime.datetime.now(), "source": "test", "value_id": 1}],
        ):
            history = obj_manager.getHistory("color_prop")

        self.assertEqual(len(history), 1)
        self.assertIsInstance(history[0]["value"], str)
        self.assertTrue(history[0]["value"].startswith("#"))
        self.assertNotIn("rgb", history[0]["value"])
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    def test_get_property_default_value(self, mock_user, mock_now):
        """Тест получения свойства с default_value"""
        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None
        
        obj_manager = ObjectManager(self.mock_object)
        
        # Создаем свойство с default_value, но без значения в БД (value_id = None)
        mock_prop = Mock()
        mock_prop.id = 1
        mock_prop.name = "test_prop"
        mock_prop.description = ""
        mock_prop.history = 0
        mock_prop.type = "int"
        mock_prop.params = json.dumps({
            "min": 0,
            "max": 100,
            "default_value": "50"
        })
        
        # Не передаем mock_value (None), чтобы value_id был None
        prop_manager = PropertyManager(1, mock_prop, None)
        obj_manager.properties["test_prop"] = prop_manager
        
        # При получении свойства должно вернуться default_value
        value = obj_manager.getProperty("test_prop")
        self.assertEqual(value, 50)  # default_value декодируется как int
        
        # Проверяем, что если свойство уже имеет значение, default_value не используется
        mock_value = Mock()
        mock_value.id = 1
        mock_value.value = "75"
        mock_value.changed = datetime.datetime.now()
        mock_value.source = "test"
        mock_value.linked = None
        
        prop_manager_with_value = PropertyManager(1, mock_prop, mock_value)
        obj_manager.properties["test_prop"] = prop_manager_with_value
        
        value = obj_manager.getProperty("test_prop")
        self.assertEqual(value, 75)  # Используется значение из БД, а не default_value
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    def test_get_property_default_value_str(self, mock_user, mock_now):
        """Тест получения свойства типа str с default_value"""
        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None
        
        obj_manager = ObjectManager(self.mock_object)
        
        # Создаем свойство типа str с default_value
        mock_prop = Mock()
        mock_prop.id = 1
        mock_prop.name = "status"
        mock_prop.description = ""
        mock_prop.history = 0
        mock_prop.type = "str"
        mock_prop.params = json.dumps({
            "default_value": "initialized"
        })
        
        prop_manager = PropertyManager(1, mock_prop, None)
        obj_manager.properties["status"] = prop_manager
        
        value = obj_manager.getProperty("status")
        self.assertEqual(value, "initialized")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    def test_get_property_default_value_enum(self, mock_user, mock_now):
        """Тест получения свойства типа enum с default_value"""
        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None
        
        obj_manager = ObjectManager(self.mock_object)
        
        # Создаем свойство типа enum с default_value
        mock_prop = Mock()
        mock_prop.id = 1
        mock_prop.name = "mode"
        mock_prop.description = ""
        mock_prop.history = 0
        mock_prop.type = "enum"
        enum_values = {
            "0": "Off",
            "1": "On",
            "2": "Auto"
        }
        mock_prop.params = json.dumps({
            "enum_values": enum_values,
            "default_value": "0"
        })
        
        prop_manager = PropertyManager(1, mock_prop, None)
        obj_manager.properties["mode"] = prop_manager
        
        value = obj_manager.getProperty("mode")
        self.assertEqual(value, "0")  # default_value для enum

        text = obj_manager.getProperty("mode", "text")
        self.assertEqual(text, "Off")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    def test_update_property(self, mock_user, mock_now):
        """Тест обновления свойства"""
        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None
        
        obj_manager = ObjectManager(self.mock_object)
        
        # Создаем свойство
        mock_prop = Mock()
        mock_prop.id = 1
        mock_prop.name = "test_prop"
        mock_prop.description = ""
        mock_prop.history = 0
        mock_prop.type = "str"
        mock_prop.params = None
        
        mock_value = Mock()
        mock_value.id = 1
        mock_value.value = "old_value"
        mock_value.changed = datetime.datetime.now()
        mock_value.source = "test"
        mock_value.linked = None
        
        prop_manager = PropertyManager(1, mock_prop, mock_value)
        prop_manager.value_id = 1
        obj_manager.properties["test_prop"] = prop_manager
        
        with patch.object(prop_manager, 'setValue') as mock_set:
            with patch.object(prop_manager, 'getValue', return_value="new_value"):
                result = obj_manager.updateProperty("test_prop", "new_value", source="test")
        
        self.assertTrue(result)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    def test_update_property_validation_error(self, mock_user, mock_now):
        """Тест обновления свойства с ошибкой валидации"""
        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None
        
        obj_manager = ObjectManager(self.mock_object)
        
        # Создаем свойство с ограничениями
        mock_prop = Mock()
        mock_prop.id = 1
        mock_prop.name = "test_prop"
        mock_prop.description = ""
        mock_prop.history = 0
        mock_prop.type = "int"
        mock_prop.params = json.dumps({"min": 0, "max": 100})
        
        mock_value = Mock()
        mock_value.id = 1
        mock_value.value = "50"
        mock_value.changed = datetime.datetime.now()
        mock_value.source = "test"
        mock_value.linked = None
        
        prop_manager = PropertyManager(1, mock_prop, mock_value)
        obj_manager.properties["test_prop"] = prop_manager
        
        # Попытка обновить невалидным значением
        result = obj_manager.updateProperty("test_prop", "150", source="test")
        
        self.assertFalse(result)  # Должно вернуть False из-за ошибки валидации
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_set_permission(self, mock_now):
        """Тест установки прав доступа"""
        mock_now.return_value = datetime.datetime.now()
        
        obj_manager = ObjectManager(self.mock_object)
        permissions = {"get": {"access_roles": ["user"]}}
        
        obj_manager.set_permission(permissions)
        
        self.assertTrue(object.__getattribute__(obj_manager, "__inited"))
        self.assertEqual(object.__getattribute__(obj_manager, "__permissions"), permissions)

    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_get_param_object_property_method(self, mock_now):
        """getParam: params объекта, свойства и метода."""
        mock_now.return_value = datetime.datetime.now()
        self.mock_object.params = json.dumps({"protected": True, "icon": "lamp"})

        obj_manager = ObjectManager(self.mock_object)

        self.assertTrue(obj_manager.getParam("protected"))
        self.assertEqual(obj_manager.getParam("icon"), "lamp")
        self.assertIsNone(obj_manager.getParam("missing"))

        mock_prop = Mock()
        mock_prop.id = 1
        mock_prop.name = "temp"
        mock_prop.description = ""
        mock_prop.history = 0
        mock_prop.type = "float"
        mock_prop.params = json.dumps({"min": 0, "icon": "thermometer"})
        mock_value = Mock()
        mock_value.id = 1
        mock_value.value = "20"
        mock_value.changed = datetime.datetime.now()
        mock_value.source = "test"
        mock_value.linked = None
        obj_manager.properties["temp"] = PropertyManager(1, mock_prop, mock_value)

        self.assertEqual(obj_manager.getParam("temp", "icon"), "thermometer")
        self.assertEqual(obj_manager.getParam("temp", "min"), 0)
        self.assertIsNone(obj_manager.getParam("temp", "missing"))

        method = MethodManager([{
            "name": "run",
            "description": "",
            "code": "pass",
            "params": json.dumps({"protected": True, "color": "#f00"}),
        }])
        obj_manager.methods["run"] = method

        self.assertTrue(obj_manager.getParam("run", "protected"))
        self.assertEqual(obj_manager.getParam("run", "color"), "#f00")
        self.assertIsNone(obj_manager.getParam("unknown", "icon"))
        self.assertIsNone(obj_manager.getParam(""))

    @patch('app.core.lib.object.objects_storage')
    def test_module_get_param_delegates_to_object_manager(self, mock_storage):
        """app.core.lib.object.getParam делегирует в ObjectManager.getParam."""
        from app.core.lib.object import getParam

        om = MagicMock()
        om.getParam.side_effect = lambda *a, **k: {
            ("protected",): True,
            ("temp", "icon"): "thermometer",
        }.get(a)
        mock_storage.getObjectByName.return_value = om

        self.assertTrue(getParam("Lamp", "protected"))
        om.getParam.assert_any_call("protected")

        self.assertEqual(getParam("Lamp.temp", "icon"), "thermometer")
        om.getParam.assert_any_call("temp", "icon")

        mock_storage.getObjectByName.return_value = None
        self.assertIsNone(getParam("Missing", "icon"))


class TestSetPropertyWithDate(unittest.TestCase):
    """Тесты для установки значения свойства с указанной датой"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self._timezone_patches = [
            patch('app.core.main.ObjectManager.convert_local_to_utc', side_effect=lambda x: x),
            patch('app.core.main.ObjectManager.convert_utc_to_local', side_effect=lambda x: x),
        ]
        for p in self._timezone_patches:
            p.start()

        self.mock_object = Mock()
        self.mock_object.id = 1
        self.mock_object.name = "test_object"
        self.mock_object.description = "Test Object"
        
        self.mock_property = Mock()
        self.mock_property.id = 1
        self.mock_property.name = "test_property"
        self.mock_property.description = "Test Property"
        self.mock_property.history = 7  # Сохраняем историю на 7 дней
        self.mock_property.type = "str"
        self.mock_property.params = None
        
        self.mock_value = Mock()
        self.mock_value.id = 1
        self.mock_value.value = "initial_value"
        self.mock_value.changed = datetime.datetime(2024, 1, 15, 10, 0, 0)
        self.mock_value.source = "initial_source"
        self.mock_value.linked = None

        self._clear_global_batch_writer()

    def _clear_global_batch_writer(self):
        import app.core.main.ObjectManager as om_module

        writer = om_module._batch_writer
        with writer._lock:
            writer._batch.clear()

    def tearDown(self):
        self._clear_global_batch_writer()
        for p in reversed(self._timezone_patches):
            p.stop()
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager.session_scope')
    @patch('app.core.main.ObjectManager._batch_writer')
    def test_set_property_with_date(self, mock_batch_writer, mock_session, mock_user, mock_now):
        """Тест установки значения с указанной датой"""
        # Устанавливаем текущее время
        current_time = datetime.datetime(2024, 1, 20, 12, 0, 0)
        mock_now.return_value = current_time
        mock_user.username = None
        
        # Мокируем сессию БД
        mock_session.return_value.__enter__.return_value = MagicMock()
        mock_session.return_value.__exit__.return_value = None
        
        obj_manager = ObjectManager(self.mock_object)
        
        # Создаем свойство с существующим значением
        prop_manager = PropertyManager(1, self.mock_property, self.mock_value)
        prop_manager.value_id = 1
        obj_manager.properties["test_property"] = prop_manager
        
        # Устанавливаем значение с указанной датой
        specified_date = datetime.datetime(2024, 1, 18, 14, 30, 0)
        result = obj_manager.setProperty("test_property", "new_value", source="test_source", changed=specified_date)
        
        self.assertTrue(result)
        # Значение должно быть обновлено
        self.assertEqual(prop_manager.value, "new_value")
        self.assertEqual(prop_manager.changed, specified_date)
        # Проверяем, что был вызван batch_writer
        self.assertTrue(mock_batch_writer.add.called)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager.session_scope')
    @patch('app.core.main.ObjectManager._batch_writer')
    def test_set_property_with_older_date_history_only(self, mock_batch_writer, mock_session, mock_user, mock_now):
        """Тест установки значения с датой старше текущей - должно обновиться только история"""
        # Устанавливаем текущее время
        current_time = datetime.datetime(2024, 1, 20, 12, 0, 0)
        mock_now.return_value = current_time
        mock_user.username = None
        
        # Мокируем сессию БД
        mock_session.return_value.__enter__.return_value = MagicMock()
        mock_session.return_value.__exit__.return_value = None
        
        obj_manager = ObjectManager(self.mock_object)
        
        # Создаем свойство с существующим значением (дата: 2024-01-15 10:00)
        prop_manager = PropertyManager(1, self.mock_property, self.mock_value)
        prop_manager.value_id = 1
        obj_manager.properties["test_property"] = prop_manager
        
        # Сохраняем текущее значение
        old_value = prop_manager.value
        old_changed = prop_manager.changed
        
        # Устанавливаем значение с датой старше текущей (2024-01-10)
        older_date = datetime.datetime(2024, 1, 10, 8, 0, 0)
        result = obj_manager.setProperty("test_property", "historical_value", source="test_source", changed=older_date)
        
        self.assertTrue(result)
        # Значение НЕ должно быть обновлено (остается старым)
        self.assertEqual(prop_manager.value, old_value)
        self.assertEqual(prop_manager.changed, old_changed)
        # Проверяем, что был вызван batch_writer для истории
        self.assertTrue(mock_batch_writer.add.called)
        
        # Проверяем, что в batch_writer была передана запись с history_only=True
        history_only_calls = [
            c[0][0] for c in mock_batch_writer.add.call_args_list
            if c and c[0] and getattr(c[0][0], "history_only", False)
        ]
        self.assertTrue(history_only_calls)
        self.assertEqual(history_only_calls[0].changed, older_date)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager.session_scope')
    def test_set_property_with_date_saves_to_history(self, mock_session, mock_user, mock_now):
        """Тест сохранения в историю с указанной датой"""
        current_time = datetime.datetime(2024, 1, 20, 12, 0, 0)
        mock_now.return_value = current_time
        mock_user.username = None
        
        # Мокируем сессию БД
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_session.return_value.__exit__.return_value = None
        
        obj_manager = ObjectManager(self.mock_object)
        
        # Создаем свойство с историей
        prop_manager = PropertyManager(1, self.mock_property, self.mock_value)
        prop_manager.value_id = 1
        obj_manager.properties["test_property"] = prop_manager
        
        # Устанавливаем значение с указанной датой
        specified_date = datetime.datetime(2024, 1, 18, 14, 30, 0)
        result = obj_manager.setProperty("test_property", "new_value", source="test_source", save_history=True, changed=specified_date)
        
        self.assertTrue(result)
        # Проверяем, что значение обновлено
        self.assertEqual(prop_manager.value, "new_value")
        self.assertEqual(prop_manager.changed, specified_date)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager.session_scope')
    def test_set_property_with_same_date_and_source_updates_history(self, mock_session_scope, mock_user, mock_now):
        """Тест обновления существующей записи истории при совпадении даты и source"""
        current_time = datetime.datetime(2024, 1, 20, 12, 0, 0)
        mock_now.return_value = current_time
        mock_user.username = None
        
        # Мокируем существующую запись истории
        existing_history = Mock()
        existing_history.value_id = 1
        existing_history.added = datetime.datetime(2024, 1, 15, 10, 0, 0)
        existing_history.source = "test_source"
        existing_history.value = "old_history_value"
        
        # Мокируем сессию БД для BatchWriter
        mock_db_session = MagicMock()
        
        # Мокируем запрос к истории
        # session.query(History).filter(...).all() - filter вызывается один раз с несколькими условиями
        mock_query_result = MagicMock()
        mock_query_result.all.return_value = [existing_history]
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query_result
        mock_db_session.query.return_value = mock_query
        mock_db_session.bulk_insert_mappings = MagicMock()
        mock_db_session.commit = MagicMock()
        
        # Настраиваем session_scope для возврата мокированной сессии
        # session_scope используется как context manager, поэтому возвращаем объект с __enter__ и __exit__
        mock_session_context = MagicMock()
        mock_session_context.__enter__ = MagicMock(return_value=mock_db_session)
        mock_session_context.__exit__ = MagicMock(return_value=None)
        # session_scope должен возвращать context manager при вызове
        mock_session_scope.return_value = mock_session_context
        
        # Используем реальный BatchWriter для тестирования логики
        from app.core.main.ObjectManager import BatchWriter
        batch_writer = BatchWriter(flush_interval=0.1)
        
        # Временно заменяем глобальный _batch_writer
        import app.core.main.ObjectManager as om_module
        original_batch_writer = om_module._batch_writer
        self._clear_global_batch_writer()
        om_module._batch_writer = batch_writer
        
        try:
            obj_manager = ObjectManager(self.mock_object)
            
            # Создаем свойство
            prop_manager = PropertyManager(1, self.mock_property, self.mock_value)
            prop_manager.value_id = 1
            obj_manager.properties["test_property"] = prop_manager
            
            # Устанавливаем значение с той же датой и source
            same_date = datetime.datetime(2024, 1, 15, 10, 0, 0)
            result = obj_manager.setProperty("test_property", "updated_value", source="test_source", save_history=True, changed=same_date)
            
            self.assertTrue(result)

            batch_writer.flush_sync()

            # Проверяем, что существующая запись истории была обновлена
            self.assertEqual(existing_history.value, "updated_value")
            self.assertEqual(existing_history.source, "test_source")
            # Проверяем, что для test_property(value_id=1) не было insert (только update)
            inserted = []
            for call in mock_db_session.bulk_insert_mappings.call_args_list:
                if len(call.args) >= 2 and isinstance(call.args[1], list):
                    inserted.extend(call.args[1])
            self.assertFalse(any(item.get("value_id") == 1 for item in inserted))
            # Проверяем, что commit был вызван
            self.assertTrue(mock_db_session.commit.called)
        finally:
            # Восстанавливаем оригинальный batch_writer
            om_module._batch_writer = original_batch_writer
            batch_writer.shutdown(wait=True)
            time.sleep(0.2)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager.session_scope')
    def test_set_property_with_same_date_different_source_creates_new_history(self, mock_session_scope, mock_user, mock_now):
        """Тест создания новой записи истории при другом source, но той же дате"""
        current_time = datetime.datetime(2024, 1, 20, 12, 0, 0)
        mock_now.return_value = current_time
        mock_user.username = None

        # Мокируем существующую запись истории с другим source
        existing_history = Mock()
        existing_history.value_id = 1
        existing_history.added = datetime.datetime(2024, 1, 15, 10, 0, 0)
        existing_history.source = "old_source"
        existing_history.value = "old_history_value"

        # Мокируем сессию БД, которую будет использовать BatchWriter
        mock_db_session = MagicMock()

        # session.query(History).filter(...).all()
        mock_query_result = MagicMock()
        mock_query_result.all.return_value = [existing_history]
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query_result
        mock_db_session.query.return_value = mock_query
        mock_db_session.bulk_insert_mappings = MagicMock()
        mock_db_session.commit = MagicMock()

        # session_scope как context manager
        mock_session_context = MagicMock()
        mock_session_context.__enter__.return_value = mock_db_session
        mock_session_context.__exit__.return_value = None
        mock_session_scope.return_value = mock_session_context

        # Используем реальный BatchWriter
        from app.core.main.ObjectManager import BatchWriter
        import app.core.main.ObjectManager as om_module

        batch_writer = BatchWriter(flush_interval=0.1)
        original_batch_writer = om_module._batch_writer
        self._clear_global_batch_writer()
        om_module._batch_writer = batch_writer

        try:
            obj_manager = ObjectManager(self.mock_object)

            # Создаем свойство
            prop_manager = PropertyManager(1, self.mock_property, self.mock_value)
            prop_manager.value_id = 1
            obj_manager.properties["test_property"] = prop_manager

            # Устанавливаем значение с той же датой, но другим source
            same_date = datetime.datetime(2024, 1, 15, 10, 0, 0)
            result = obj_manager.setProperty(
                "test_property",
                "new_value",
                source="new_source",
                save_history=True,
                changed=same_date,
            )

            self.assertTrue(result)

            batch_writer.flush_sync()

            # Должна быть создана новая запись истории (bulk_insert_mappings вызван)
            self.assertTrue(mock_db_session.bulk_insert_mappings.called)
            # Старая запись не должна быть изменена
            self.assertEqual(existing_history.value, "old_history_value")
            self.assertEqual(existing_history.source, "old_source")
            self.assertTrue(mock_db_session.commit.called)
        finally:
            om_module._batch_writer = original_batch_writer
            batch_writer.shutdown(wait=True)
            time.sleep(0.2)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager.session_scope')
    @patch('app.core.main.ObjectManager._batch_writer')
    def test_set_property_without_date_uses_current_time(self, mock_batch_writer, mock_session, mock_user, mock_now):
        """Тест установки значения без указания даты - должна использоваться текущая дата"""
        current_time = datetime.datetime(2024, 1, 20, 12, 0, 0)
        mock_now.return_value = current_time
        mock_user.username = None
        
        # Мокируем сессию БД
        mock_session.return_value.__enter__.return_value = MagicMock()
        mock_session.return_value.__exit__.return_value = None
        
        obj_manager = ObjectManager(self.mock_object)
        
        # Создаем свойство
        prop_manager = PropertyManager(1, self.mock_property, self.mock_value)
        prop_manager.value_id = 1
        obj_manager.properties["test_property"] = prop_manager
        
        # Устанавливаем значение без указания даты
        result = obj_manager.setProperty("test_property", "new_value", source="test_source")
        
        self.assertTrue(result)
        # Должна использоваться текущая дата
        self.assertEqual(prop_manager.changed, current_time)
        self.assertEqual(prop_manager.value, "new_value")


if __name__ == '__main__':
    unittest.main()

