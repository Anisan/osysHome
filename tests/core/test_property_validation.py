"""
Тесты для валидации ограничений свойств в PropertyManager

Проверяет:
- Валидацию min/max для int и float
- Валидацию regexp для str
- Валидацию enum_values для enum
- Обработку ошибок валидации
"""
import unittest
from unittest.mock import Mock, patch
import json
import datetime

from app.core.main.ObjectManager import PropertyManager
from app.core.models.Clasess import Property, Value


class TestPropertyValidation(unittest.TestCase):
    """Тесты валидации ограничений свойств"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.object_id = 1
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_int_min_validation(self, mock_now):
        """Тест валидации минимального значения для int"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "temperature"
        mock_property.description = "Temperature"
        mock_property.history = 0
        mock_property.type = "int"
        mock_property.params = json.dumps({"min": 0, "max": 100})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Валидные значения
        self.assertEqual(prop_manager._decodeValue("0"), 0)
        self.assertEqual(prop_manager._decodeValue("50"), 50)
        self.assertEqual(prop_manager._decodeValue("100"), 100)
        
        # Невалидные значения
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("-1")
        self.assertIn("less than minimum", str(context.exception))
        
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("101")
        self.assertIn("greater than maximum", str(context.exception))
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_int_max_validation(self, mock_now):
        """Тест валидации максимального значения для int"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "counter"
        mock_property.description = "Counter"
        mock_property.history = 0
        mock_property.type = "int"
        mock_property.params = json.dumps({"max": 1000})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Валидные значения
        self.assertEqual(prop_manager._decodeValue("0"), 0)
        self.assertEqual(prop_manager._decodeValue("1000"), 1000)
        
        # Невалидное значение
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("1001")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_float_min_max_validation(self, mock_now):
        """Тест валидации min/max для float"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "voltage"
        mock_property.description = "Voltage"
        mock_property.history = 0
        mock_property.type = "float"
        mock_property.params = json.dumps({"min": 0.0, "max": 240.0, "decimals": 2})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Валидные значения
        self.assertEqual(prop_manager._decodeValue("0.0"), 0.0)
        self.assertEqual(prop_manager._decodeValue("120.5"), 120.5)
        self.assertEqual(prop_manager._decodeValue("240.0"), 240.0)
        
        # Невалидные значения
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("-0.1")
        self.assertIn("less than minimum", str(context.exception))
        
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("240.1")
        self.assertIn("greater than maximum", str(context.exception))
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_str_regexp_validation(self, mock_now):
        """Тест валидации строки по регулярному выражению"""
        mock_now.return_value = datetime.datetime.now()
        
        # Email pattern
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "email"
        mock_property.description = "Email"
        mock_property.history = 0
        mock_property.type = "str"
        mock_property.params = json.dumps({
            "regexp": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
        })
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Валидные значения
        self.assertEqual(prop_manager._decodeValue("test@example.com"), "test@example.com")
        self.assertEqual(prop_manager._decodeValue("user.name@domain.co.uk"), "user.name@domain.co.uk")
        
        # Невалидные значения
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("invalid-email")
        self.assertIn("does not match pattern", str(context.exception))
        
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("@example.com")
        self.assertIn("does not match pattern", str(context.exception))
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_str_regexp_validation_code_format(self, mock_now):
        """Тест валидации формата кода (например, ABC-1234)"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "code"
        mock_property.description = "Code"
        mock_property.history = 0
        mock_property.type = "str"
        mock_property.params = json.dumps({
            "regexp": "^[A-Z]{3}-\\d{4}$"
        })
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Валидные значения
        self.assertEqual(prop_manager._decodeValue("ABC-1234"), "ABC-1234")
        self.assertEqual(prop_manager._decodeValue("XYZ-0000"), "XYZ-0000")
        
        # Невалидные значения
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("abc-1234")  # lowercase
        
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("ABC-123")  # недостаточно цифр
        
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("AB-1234")  # недостаточно букв
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_enum_validation(self, mock_now):
        """Тест валидации значений enum"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "mode"
        mock_property.description = "Mode"
        mock_property.history = 0
        mock_property.type = "enum"
        enum_values = {
            "0": "Off",
            "1": "On",
            "2": "Auto",
            "3": "Manual"
        }
        mock_property.params = json.dumps({"enum_values": enum_values})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Валидные значения
        self.assertEqual(prop_manager._decodeValue("0"), "0")
        self.assertEqual(prop_manager._decodeValue("1"), "1")
        self.assertEqual(prop_manager._decodeValue("2"), "2")
        self.assertEqual(prop_manager._decodeValue("3"), "3")
        
        # Невалидные значения
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("4")
        self.assertIn("not in allowed enum values", str(context.exception))
        
        with self.assertRaises(ValueError) as context:
            prop_manager._decodeValue("invalid")
        self.assertIn("not in allowed enum values", str(context.exception))
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_validation_skipped_on_init(self, mock_now):
        """Тест, что валидация пропускается при init=True"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "temperature"
        mock_property.description = "Temperature"
        mock_property.history = 0
        mock_property.type = "int"
        mock_property.params = json.dumps({"min": 0, "max": 100})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # При init=True валидация не выполняется
        # Это позволяет загружать значения из БД даже если они не соответствуют текущим ограничениям
        result = prop_manager._decodeValue("150", init=True)
        self.assertEqual(result, 150)  # Значение принято без ошибки

    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_int_init_coerces_float_string(self, mock_now):
        """При init=True int-свойство не падает на float-строке из БД."""
        mock_now.return_value = datetime.datetime.now()

        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "value"
        mock_property.description = "Value"
        mock_property.history = 0
        mock_property.type = "int"
        mock_property.params = None

        prop_manager = PropertyManager(self.object_id, mock_property, None)

        self.assertEqual(prop_manager._decodeValue("23.5", init=True), 23)
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager._batch_writer')
    def test_set_value_with_validation_error(self, mock_batch_writer, mock_user, mock_now):
        """Тест установки значения с ошибкой валидации"""
        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "temperature"
        mock_property.description = "Temperature"
        mock_property.history = 0
        mock_property.type = "int"
        mock_property.params = json.dumps({"min": 0, "max": 100})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Попытка установить невалидное значение должна вызвать ValueError
        with self.assertRaises(ValueError):
            prop_manager.setValue(150)  # Превышает max=100
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager._batch_writer')
    def test_set_value_with_valid_constraints(self, mock_batch_writer, mock_user, mock_now):
        """Тест установки валидного значения с ограничениями"""
        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "temperature"
        mock_property.description = "Temperature"
        mock_property.history = 0
        mock_property.type = "int"
        mock_property.params = json.dumps({"min": 0, "max": 100})
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        prop_manager.value_id = 1
        
        # Установка валидного значения должна пройти успешно
        prop_manager.setValue(50)
        
        self.assertEqual(prop_manager.value, 50)
        mock_batch_writer.add.assert_called_once()
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_multiple_constraints_combined(self, mock_now):
        """Тест комбинации нескольких ограничений"""
        mock_now.return_value = datetime.datetime.now()
        
        # Float с min, max и decimals
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "percentage"
        mock_property.description = "Percentage"
        mock_property.history = 0
        mock_property.type = "float"
        mock_property.params = json.dumps({
            "min": 0.0,
            "max": 100.0,
            "decimals": 2
        })
        
        prop_manager = PropertyManager(self.object_id, mock_property, None)
        
        # Валидное значение с округлением
        result = prop_manager._decodeValue("50.12345")
        self.assertEqual(result, 50.12)  # Округлено до 2 знаков
        
        # Проверка min/max после округления
        self.assertEqual(prop_manager._decodeValue("0.0"), 0.0)
        self.assertEqual(prop_manager._decodeValue("100.0"), 100.0)
        
        # Невалидные значения
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("-0.01")
        
        with self.assertRaises(ValueError):
            prop_manager._decodeValue("100.01")


if __name__ == '__main__':
    unittest.main()

