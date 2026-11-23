"""
Примеры использования тестов для демонстрации основных сценариев

Эти тесты демонстрируют типичные случаи использования классов из ObjectManager.
"""
import unittest
from unittest.mock import Mock, patch
import json
import datetime

from app.core.main.ObjectManager import PropertyManager, ObjectManager
from app.core.models.Clasess import Property, Value, Object


class TestExamples(unittest.TestCase):
    """Примеры использования для документации"""
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_example_temperature_sensor(self, mock_now):
        """Пример: Датчик температуры с ограничениями"""
        mock_now.return_value = datetime.datetime.now()
        
        # Создаем свойство температуры с ограничениями
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "temperature"
        mock_property.description = "Room Temperature"
        mock_property.history = 7  # Хранить историю 7 дней
        mock_property.type = "float"
        mock_property.params = json.dumps({
            "min": -50.0,
            "max": 150.0,
            "decimals": 1,
            "default_value": "20.0",
            "icon": "fas fa-thermometer-half",
            "color": "#FF5722"
        })
        
        prop_manager = PropertyManager(1, mock_property, None)
        prop_manager.value_id = 1  # Устанавливаем value_id для сохранения
        
        # Установка валидного значения
        with patch('app.core.main.ObjectManager._batch_writer'):
            prop_manager.setValue(23.5)
            self.assertEqual(prop_manager.value, 23.5)
        
        # Попытка установить невалидное значение
        with self.assertRaises(ValueError):
            prop_manager.setValue(200.0)  # Превышает максимум
        
        with self.assertRaises(ValueError):
            prop_manager.setValue(-60.0)  # Ниже минимума
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_example_enum_switch(self, mock_now):
        """Пример: Переключатель с enum значениями"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "switch"
        mock_property.description = "Light Switch"
        mock_property.history = 0
        mock_property.type = "enum"
        enum_values = {
            "0": "Выключено",
            "1": "Включено",
            "2": "Автоматически"
        }
        mock_property.params = json.dumps({"enum_values": enum_values})
        
        prop_manager = PropertyManager(1, mock_property, None)
        prop_manager.value_id = 1
        
        # Установка валидных значений
        with patch('app.core.main.ObjectManager._batch_writer'):
            prop_manager.setValue("0")
            self.assertEqual(prop_manager.value, "0")
            
            prop_manager.setValue("1")
            self.assertEqual(prop_manager.value, "1")
        
        # Попытка установить невалидное значение
        with self.assertRaises(ValueError):
            prop_manager.setValue("3")  # Не существует в enum
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_example_email_validation(self, mock_now):
        """Пример: Валидация email адреса"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "email"
        mock_property.description = "Email Address"
        mock_property.history = 0
        mock_property.type = "str"
        mock_property.params = json.dumps({
            "regexp": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
        })
        
        prop_manager = PropertyManager(1, mock_property, None)
        prop_manager.value_id = 1
        
        # Валидные email
        with patch('app.core.main.ObjectManager._batch_writer'):
            prop_manager.setValue("user@example.com")
            self.assertEqual(prop_manager.value, "user@example.com")
            
            prop_manager.setValue("test.user+tag@domain.co.uk")
            self.assertEqual(prop_manager.value, "test.user+tag@domain.co.uk")
        
        # Невалидные email
        with self.assertRaises(ValueError):
            prop_manager.setValue("invalid-email")
        
        with self.assertRaises(ValueError):
            prop_manager.setValue("@example.com")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_example_read_only_property(self, mock_now):
        """Пример: Read-only свойство"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "version"
        mock_property.description = "System Version"
        mock_property.history = 0
        mock_property.type = "str"
        mock_property.params = json.dumps({
            "read_only": True,
            "default_value": "1.0.0"
        })
        
        prop_manager = PropertyManager(1, mock_property, None)
        
        # Получение значения по умолчанию
        self.assertEqual(prop_manager.value, "1.0.0")
        
        # Попытка изменить read-only свойство
        with self.assertRaises(PermissionError):
            prop_manager.setValue("2.0.0")
    
    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_example_default_value(self, mock_now):
        """Пример: Использование значения по умолчанию"""
        mock_now.return_value = datetime.datetime.now()
        
        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "counter"
        mock_property.description = "Counter"
        mock_property.history = 0
        mock_property.type = "int"
        mock_property.params = json.dumps({
            "min": 0,
            "max": 100,
            "default_value": "50"
        })
        
        # Создаем PropertyManager без значения (value_id = None)
        prop_manager = PropertyManager(1, mock_property, None)
        
        # При получении значения должно вернуться default_value
        self.assertEqual(prop_manager.value, 50)
        
        # После установки значения default_value больше не используется
        prop_manager.value_id = 1  # Имитируем существующую запись в БД
        with patch('app.core.main.ObjectManager._batch_writer'):
            prop_manager.setValue(75)
            self.assertEqual(prop_manager.value, 75)


if __name__ == '__main__':
    unittest.main()

