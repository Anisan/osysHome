"""
Тесты для расширенных валидаций свойств в PropertyManager

Проверяет:
- Валидацию step/discreteness для int и float
- Валидацию allowed_values для всех типов
- Валидацию rate_limit для ограничения частоты изменений
- Валидацию depends_on для зависимостей между свойствами
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import datetime
import time

from app.core.main.ObjectManager import PropertyManager, ObjectManager
from app.core.models.Clasess import Property, Value, Object


class TestStepValidation(unittest.TestCase):
    """Тесты валидации step/discreteness"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.object_id = 1
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_int_step_validation_basic(self, mock_now):
        """Тест базовой валидации step для int"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "brightness"
        mock_property.description = "Brightness"
        mock_property.history = 0
        mock_property.type = "int"
        mock_property.params = json.dumps({"min": 0, "max": 100, "step": 10})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Валидные значения (кратны 10)
        self.assertEqual(prop_manager._decodeValue("0"), 0)
        self.assertEqual(prop_manager._decodeValue("10"), 10)
        self.assertEqual(prop_manager._decodeValue("50"), 50)
        self.assertEqual(prop_manager._decodeValue("100"), 100)
        
        # Невалидные значения (не кратны 10)
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("5")
        self.assertIn("not aligned with step", str(context.exception))
        
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("37")
        self.assertIn("not aligned with step", str(context.exception))
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_int_step_validation_custom_base(self, mock_now):
        """Тест валидации step с пользовательской базой"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "level"
        mock_property.description = "Level"
        mock_property.history = 0
        mock_property.type = "int"
        # База 5, шаг 10: разрешены 5, 15, 25, 35...
        mock_property.params = json.dumps({"min": 5, "max": 95, "step": 10})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Валидные значения
        self.assertEqual(prop_manager._decodeValue("5"), 5)
        self.assertEqual(prop_manager._decodeValue("15"), 15)
        self.assertEqual(prop_manager._decodeValue("25"), 25)
        self.assertEqual(prop_manager._decodeValue("95"), 95)
        
        # Невалидные значения
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("10")  # не кратно базе+шаг
        
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("20")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_float_step_validation(self, mock_now):
        """Тест валидации step для float"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "temperature"
        mock_property.description = "Temperature"
        mock_property.history = 0
        mock_property.type = "float"
        mock_property.params = json.dumps({"min": 0.0, "max": 100.0, "step": 0.5, "decimals": 1})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Валидные значения (кратны 0.5)
        self.assertEqual(prop_manager._decodeValue("0.0"), 0.0)
        self.assertEqual(prop_manager._decodeValue("0.5"), 0.5)
        self.assertEqual(prop_manager._decodeValue("1.0"), 1.0)
        self.assertEqual(prop_manager._decodeValue("50.5"), 50.5)
        self.assertEqual(prop_manager._decodeValue("100.0"), 100.0)
        
        # Невалидные значения (не кратны 0.5)
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("0.3")
        self.assertIn("not aligned with step", str(context.exception))
        
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("1.7")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_step_validation_skipped_on_init(self, mock_now):
        """Тест, что step валидация пропускается при init=True"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "brightness"
        mock_property.description = "Brightness"
        mock_property.history = 0
        mock_property.type = "int"
        mock_property.params = json.dumps({"min": 0, "max": 100, "step": 10})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # При init=True step валидация не выполняется
        result = prop_manager._decodeValue("37", init=True)
        self.assertEqual(result, 37)


class TestAllowedValues(unittest.TestCase):
    """Тесты валидации allowed_values"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.object_id = 1
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_allowed_values_int(self, mock_now):
        """Тест allowed_values для int"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "priority"
        mock_property.description = "Priority"
        mock_property.history = 0
        mock_property.type = "int"
        mock_property.params = json.dumps({"allowed_values": [1, 2, 3, 5, 10]})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Валидные значения
        self.assertEqual(prop_manager._decodeValue("1"), 1)
        self.assertEqual(prop_manager._decodeValue("2"), 2)
        self.assertEqual(prop_manager._decodeValue("10"), 10)
        
        # Невалидные значения
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("4")
        self.assertIn("not in allowed values", str(context.exception))
        
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("100")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_allowed_values_float(self, mock_now):
        """Тест allowed_values для float"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "multiplier"
        mock_property.description = "Multiplier"
        mock_property.history = 0
        mock_property.type = "float"
        mock_property.params = json.dumps({"allowed_values": [0.5, 1.0, 1.5, 2.0]})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Валидные значения
        self.assertEqual(prop_manager._decodeValue("0.5"), 0.5)
        self.assertEqual(prop_manager._decodeValue("1.0"), 1.0)
        self.assertEqual(prop_manager._decodeValue("2.0"), 2.0)
        
        # Невалидные значения
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("1.2")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_allowed_values_str(self, mock_now):
        """Тест allowed_values для str"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "color"
        mock_property.description = "Color"
        mock_property.history = 0
        mock_property.type = "str"
        mock_property.params = json.dumps({"allowed_values": ["red", "green", "blue", "yellow"]})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Валидные значения
        self.assertEqual(prop_manager._decodeValue("red"), "red")
        self.assertEqual(prop_manager._decodeValue("blue"), "blue")
        
        # Невалидные значения
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("purple")
        self.assertIn("not in allowed values", str(context.exception))
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_allowed_values_skipped_for_enum(self, mock_now):
        """Тест, что allowed_values игнорируется для enum (используется enum_values)"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "mode"
        mock_property.description = "Mode"
        mock_property.history = 0
        mock_property.type = "enum"
        mock_property.params = json.dumps({
            "enum_values": {"0": "Off", "1": "On"},
            "allowed_values": ["2", "3"]  # Должно игнорироваться
        })
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # enum_values имеет приоритет
        self.assertEqual(prop_manager._decodeValue("0"), "0")
        
        # allowed_values игнорируется для enum
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("2")


class TestRateLimit(unittest.TestCase):
    """Тесты валидации rate_limit"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.object_id = 1
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager._batch_writer')
    def test_rate_limit_prevents_fast_changes(self, mock_batch_writer, mock_user, mock_now):
        """Тест, что rate_limit предотвращает быстрые изменения"""
        base_time = datetime.datetime(2025, 1, 1, 12, 0, 0)
        mock_now.return_value = base_time
        mock_user.username = None
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "button"
        mock_property.description = "Button"
        mock_property.history = 0
        mock_property.type = "int"
        mock_property.params = json.dumps({"rate_limit": 5.0})  # 5 секунд между изменениями
        
        mock_value = Mock()
        mock_value.id = 1
        mock_value.value = "0"
        mock_value.changed = base_time
        mock_value.source = None
        mock_value.linked = None
        
        prop_manager = PropertyManager(self.object_id, mock_property, mock_value)
        
        # Первое изменение должно пройти
        mock_now.return_value = base_time + datetime.timedelta(seconds=6)
        prop_manager.setValue(1)
        self.assertEqual(prop_manager.value, 1)
        
        # Попытка изменить слишком быстро (через 2 секунды)
        mock_now.return_value = base_time + datetime.timedelta(seconds=8)
        with self.assertRaises(ValueError) as context:
            prop_manager.setValue(2)
        self.assertIn("can be changed only once per", str(context.exception))
        self.assertIn("5", str(context.exception))
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager._batch_writer')
    def test_rate_limit_allows_after_timeout(self, mock_batch_writer, mock_user, mock_now):
        """Тест, что rate_limit разрешает изменения после таймаута"""
        base_time = datetime.datetime(2025, 1, 1, 12, 0, 0)
        mock_now.return_value = base_time
        mock_user.username = None
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "button"
        mock_property.description = "Button"
        mock_property.history = 0
        mock_property.type = "int"
        mock_property.params = json.dumps({"rate_limit": 3.0})
        
        mock_value = Mock()
        mock_value.id = 1
        mock_value.value = "0"
        mock_value.changed = base_time
        mock_value.source = None
        mock_value.linked = None
        
        prop_manager = PropertyManager(self.object_id, mock_property, mock_value)
        
        # Изменение через 4 секунды (больше 3) должно пройти
        mock_now.return_value = base_time + datetime.timedelta(seconds=4)
        prop_manager.setValue(1)
        self.assertEqual(prop_manager.value, 1)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager._batch_writer')
    def test_rate_limit_bypass(self, mock_batch_writer, mock_user, mock_now):
        """Тест обхода rate_limit с параметром bypass_rate_limit"""
        base_time = datetime.datetime(2025, 1, 1, 12, 0, 0)
        mock_now.return_value = base_time
        mock_user.username = None
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "button"
        mock_property.description = "Button"
        mock_property.history = 0
        mock_property.type = "int"
        mock_property.params = json.dumps({"rate_limit": 10.0})
        
        mock_value = Mock()
        mock_value.id = 1
        mock_value.value = "0"
        mock_value.changed = base_time
        mock_value.source = None
        mock_value.linked = None
        
        prop_manager = PropertyManager(self.object_id, mock_property, mock_value)
        
        # Изменение сразу с bypass=True должно пройти
        mock_now.return_value = base_time + datetime.timedelta(seconds=1)
        prop_manager.setValue(1, bypass_rate_limit=True)
        self.assertEqual(prop_manager.value, 1)


class TestDependsOn(unittest.TestCase):
    """Тесты валидации depends_on"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.object_id = 1
    
    @patch('app.core.main.ObjectManager.session_scope')
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_depends_on_simple_equals(self, mock_now, mock_session):
        """Тест простой зависимости с условием equals"""
        mock_now.return_value = datetime.datetime.now()
        
        # Создаем mock объект
        mock_object = Mock(spec=Object)
        mock_object.id = 1
        mock_object.name = "heater"
        mock_object.description = "Heater"
        
        obj_manager = ObjectManager(mock_object)
        obj_manager._logger = Mock()
        
        # Создаем свойство "enabled"
        mock_prop_enabled = Mock()
        mock_prop_enabled.id = 1
        mock_prop_enabled.name = "enabled"
        mock_prop_enabled.description = "Enabled"
        mock_prop_enabled.history = 0
        mock_prop_enabled.type = "bool"
        mock_prop_enabled.params = None
        
        mock_value_enabled = Mock()
        mock_value_enabled.id = 1
        mock_value_enabled.value = "False"
        mock_value_enabled.changed = mock_now.return_value
        mock_value_enabled.source = None
        mock_value_enabled.linked = None
        
        prop_enabled = PropertyManager(self.object_id, mock_prop_enabled, mock_value_enabled)
        obj_manager.properties["enabled"] = prop_enabled
        
        # Создаем свойство "power" которое зависит от "enabled"
        mock_prop_power = Mock()
        mock_prop_power.id = 2
        mock_prop_power.name = "power"
        mock_prop_power.description = "Power"
        mock_prop_power.history = 0
        mock_prop_power.type = "int"
        mock_prop_power.params = json.dumps({
            "min": 0,
            "max": 100,
            "depends_on": {
                "property": "enabled",
                "value": True,
                "condition": "equals"
            }
        })
        
        prop_power = PropertyManager(self.object_id, mock_prop_power, None)
        obj_manager.properties["power"] = prop_power
        
        # Попытка установить power когда enabled=False должна вызвать ошибку
        with self.assertRaises(ValueError) as context:
            obj_manager._validate_dependencies("power", 50, prop_power.params['depends_on'])
        self.assertIn("depends on", str(context.exception))
    
    @patch('app.core.main.ObjectManager.session_scope')
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_depends_on_greater_than(self, mock_now, mock_session):
        """Тест зависимости с условием greater_than"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_object = Mock(spec=Object)
        mock_object.id = 1
        mock_object.name = "climate"
        mock_object.description = "Climate"
        
        obj_manager = ObjectManager(mock_object)
        obj_manager._logger = Mock()
        
        # Создаем свойство "temperature"
        mock_prop_temp = Mock()
        mock_prop_temp.id = 1
        mock_prop_temp.name = "temperature"
        mock_prop_temp.description = "Temperature"
        mock_prop_temp.history = 0
        mock_prop_temp.type = "float"
        mock_prop_temp.params = None
        
        mock_value_temp = Mock()
        mock_value_temp.id = 1
        mock_value_temp.value = "10.0"
        mock_value_temp.changed = mock_now.return_value
        mock_value_temp.source = None
        mock_value_temp.linked = None
        
        prop_temp = PropertyManager(self.object_id, mock_prop_temp, mock_value_temp)
        obj_manager.properties["temperature"] = prop_temp
        
        # Зависимость: можно установить только если temperature > 15
        dependency = {
            "property": "temperature",
            "value": 15.0,
            "condition": "greater_than",
            "error_message": "Temperature must be above 15°C"
        }
        
        # Temperature = 10, должна быть ошибка
        with self.assertRaises(ValueError) as context:
            obj_manager._validate_dependencies("fan_speed", 100, dependency)
        self.assertIn("Temperature must be above 15", str(context.exception))
    
    @patch('app.core.main.ObjectManager.session_scope')
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_depends_on_multiple_dependencies(self, mock_now, mock_session):
        """Тест множественных зависимостей"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_object = Mock(spec=Object)
        mock_object.id = 1
        mock_object.name = "device"
        mock_object.description = "Device"
        
        obj_manager = ObjectManager(mock_object)
        obj_manager._logger = Mock()
        
        # Создаем свойство "enabled"
        mock_prop_enabled = Mock()
        mock_prop_enabled.id = 1
        mock_prop_enabled.name = "enabled"
        mock_prop_enabled.description = "Enabled"
        mock_prop_enabled.history = 0
        mock_prop_enabled.type = "bool"
        mock_prop_enabled.params = None
        
        mock_value_enabled = Mock()
        mock_value_enabled.id = 1
        mock_value_enabled.value = "True"
        mock_value_enabled.changed = mock_now.return_value
        mock_value_enabled.source = None
        mock_value_enabled.linked = None
        
        prop_enabled = PropertyManager(self.object_id, mock_prop_enabled, mock_value_enabled)
        obj_manager.properties["enabled"] = prop_enabled
        
        # Создаем свойство "mode"
        mock_prop_mode = Mock()
        mock_prop_mode.id = 2
        mock_prop_mode.name = "mode"
        mock_prop_mode.description = "Mode"
        mock_prop_mode.history = 0
        mock_prop_mode.type = "str"
        mock_prop_mode.params = None
        
        mock_value_mode = Mock()
        mock_value_mode.id = 2
        mock_value_mode.value = "auto"
        mock_value_mode.changed = mock_now.return_value
        mock_value_mode.source = None
        mock_value_mode.linked = None
        
        prop_mode = PropertyManager(self.object_id, mock_prop_mode, mock_value_mode)
        obj_manager.properties["mode"] = prop_mode
        
        # Зависимости: enabled=True И mode="manual"
        dependencies = [
            {"property": "enabled", "value": True, "condition": "equals"},
            {"property": "mode", "value": "manual", "condition": "equals"}
        ]
        
        # enabled=True но mode=auto, должна быть ошибка на второй зависимости
        with self.assertRaises(ValueError) as context:
            obj_manager._validate_dependencies("speed", 100, dependencies)
        self.assertIn("mode", str(context.exception))


class TestCombinedValidations(unittest.TestCase):
    """Тесты комбинаций различных валидаций"""
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_step_and_allowed_values(self, mock_now):
        """Тест комбинации step и allowed_values"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "value"
        mock_property.description = "Value"
        mock_property.history = 0
        mock_property.type = "int"
        # step=5 разрешает 0,5,10,15,20... но allowed_values ограничивает до 5,10,15
        mock_property.params = json.dumps({
            "min": 0,
            "max": 20,
            "step": 5,
            "allowed_values": [5, 10, 15]
        })
        
        prop_manager = PropertyManager(1, mock_property, None)
        
        # Валидные: удовлетворяют и step, и allowed_values
        self.assertEqual(prop_manager._decodeValue("5"), 5)
        self.assertEqual(prop_manager._decodeValue("10"), 10)
        self.assertEqual(prop_manager._decodeValue("15"), 15)
        
        # 0 удовлетворяет step, но не в allowed_values
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("0")
        self.assertIn("not in allowed values", str(context.exception))
        
        # 7 не удовлетворяет step
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("7")
        self.assertIn("not aligned with step", str(context.exception))


if __name__ == '__main__':
    unittest.main()
