# Документация по параметрам свойств

## Обзор

Поле `params` в свойствах позволяет хранить дополнительные параметры для валидации, визуального отображения и управления свойствами.

## Общие параметры (для всех типов)

### icon
**Тип:** `string`  
**Описание:** Класс иконки FontAwesome для отображения свойства  
**Пример:**
```json
{
  "icon": "fas fa-thermometer-half"
}
```

### color
**Тип:** `string`  
**Описание:** Цвет для отображения свойства (hex, rgb, named colors)  
**Пример:**
```json
{
  "color": "#FF5722"
}
```

### sort_order
**Тип:** `integer`  
**Описание:** Порядок сортировки свойства в списке (меньше = выше)  
**Пример:**
```json
{
  "sort_order": 10
}
```

### default_value
**Тип:** `any`  
**Описание:** Значение по умолчанию, которое возвращается если свойство никогда не было установлено  
**Поведение:**
- Если записи Value нет в БД → возвращается `default_value`
- Если запись есть, но значение = `None` → возвращается `None` (пользователь явно установил пустое значение)

**Пример:**
```json
{
  "default_value": "0"
}
```

**Использование:**
```python
# Свойство никогда не устанавливалось
value = obj.getProperty("counter")  # Вернет "0" (default_value)

# Установим значение
obj.setProperty("counter", "5")
value = obj.getProperty("counter")  # Вернет "5"

# Установим явно None
obj.setProperty("counter", None)
value = obj.getProperty("counter")  # Вернет None (не default_value!)
```

### read_only
**Тип:** `boolean`  
**Описание:** Защита свойства от изменения  
**Пример:**
```json
{
  "read_only": true
}
```

## Параметры валидации по типам

### Тип: int

#### min
**Описание:** Минимально допустимое значение  
**Пример:**
```json
{
  "min": 0
}
```

#### max
**Описание:** Максимально допустимое значение  
**Пример:**
```json
{
  "max": 100
}
```

**Полный пример для int:**
```json
{
  "min": 0,
  "max": 100,
  "default_value": "50",
  "icon": "fas fa-hashtag",
  "color": "#2196F3"
}
```

### Тип: float

#### min
**Описание:** Минимально допустимое значение  

#### max
**Описание:** Максимально допустимое значение  

#### decimals
**Описание:** Количество знаков после запятой  
**Пример:**
```json
{
  "decimals": 2
}
```

**Полный пример для float:**
```json
{
  "min": 0.0,
  "max": 100.0,
  "decimals": 2,
  "default_value": "23.5",
  "icon": "fas fa-thermometer-half",
  "color": "#FF5722"
}
```

### Тип: str

#### regexp
**Описание:** Регулярное выражение для валидации строки  
**Пример:**
```json
{
  "regexp": "^[A-Za-z0-9_]+$"
}
```

**Полный пример для str:**
```json
{
  "regexp": "^[A-Z]{3}-\\d{4}$",
  "default_value": "ABC-0001",
  "icon": "fas fa-text",
  "color": "#4CAF50"
}
```

### Тип: enum

Для enum типа значения **обязательно** задаются в отдельном поле `enum_values` внутри params:

**Пример:**
```json
{
  "enum_values": {
    "0": "Выключено",
    "1": "Включено",
    "2": "Ошибка"
  },
  "icon": "fas fa-toggle-on",
  "color": "#9C27B0",
  "default_value": "0"
}
```

> ⚠️ **Важно:** 
> - Enum значения **должны** быть в поле `enum_values`
> - Старый формат (значения в корне params) **не поддерживается**
> - Это позволяет использовать любые ключи как enum значения без конфликтов с системными параметрами

### Тип: color

`color` хранится в универсальном виде внутри БД и отдается в формате из `params.read_format`. Подробное руководство: [COLOR_TYPE_USAGE.ru.md](COLOR_TYPE_USAGE.ru.md).

#### Универсальный формат хранения

```json
{
  "xy": [0.458312, 0.410201],
  "rgb": [84, 102, 150]
}
```

Дополнительно могут храниться: `hs`, `hsv`, `hsl`, `hsb`, `color_temp`, `mired`.

#### Параметры color

```json
{
  "read_format": "canonical",
  "write_format": "auto",
  "color_temp_unit": "kelvin",
  "hue_scale": 360,
  "sat_scale": 100
}
```

- `read_format`: `canonical`, `hex`, `rgb`, `xy`, `hs`, `hsv`, `hsl`, `hsb`, `color_temp`, `zigbee2mqtt`
- `write_format`: `auto`, `hex`, `rgb`, `xy`, `hs`, `hsv`, `hsl`, `hsb`, `color_temp`, `zigbee2mqtt`
- `color_temp_unit`: `kelvin` или `mired`
- `hue_scale`: `360` или `254`
- `sat_scale`: `100` или `254`

#### Пример для Zigbee2MQTT

```json
{
  "read_format": "zigbee2mqtt",
  "write_format": "auto",
  "hue_scale": 360,
  "sat_scale": 100
}
```

#### Пример для UI/API

```json
{
  "read_format": "hex",
  "write_format": "hex"
}
```

#### Важно

- Яркость (`brightness`, `level`) рекомендуется хранить отдельным свойством.
- Если `write_format != auto`, формат входных данных проверяется строго.
- Конвертации выполняются через `app/core/lib/converters/color.py`.

## Расширенные параметры валидации

### step (Дискретность)

**Применимо к:** `int`, `float`  
**Описание:** Задает шаг дискретности значений. Значение должно быть кратно шагу относительно базовой точки (min или 0).

**Поведение:**
- Для `int`: значение должно быть кратно шагу: `(value - base) % step == 0`
- Для `float`: учитывается погрешность вычислений с плавающей точкой (1e-9)
- База определяется параметром `min`, если он есть, иначе 0

**Примеры:**

```json
{
  "min": 0,
  "max": 100,
  "step": 10
}
```
Допустимые значения: 0, 10, 20, 30, ..., 100

```json
{
  "min": 5,
  "max": 95,
  "step": 10
}
```
Допустимые значения: 5, 15, 25, 35, ..., 95

```json
{
  "min": 0.0,
  "max": 100.0,
  "step": 0.5,
  "decimals": 1
}
```
Допустимые значения: 0.0, 0.5, 1.0, 1.5, ..., 100.0

**Использование:**
```python
# Яркость светодиода с шагом 10%
obj.setProperty("brightness", 50)  # OK: 50 кратно 10
obj.setProperty("brightness", 37)  # ValueError: not aligned with step

# Температура термостата с шагом 0.5°C
obj.setProperty("target_temp", 22.5)  # OK
obj.setProperty("target_temp", 22.3)  # ValueError: not aligned with step
```

### allowed_values (Разрешенные значения)

**Применимо к:** всем типам кроме `enum` (для enum используйте `enum_values`)  
**Тип:** `list`  
**Описание:** Список конкретных разрешенных значений. Полезно для ограниченного набора допустимых значений.

**Примеры:**

```json
{
  "allowed_values": [1, 2, 3, 5, 10]
}
```
Только эти целые числа разрешены

```json
{
  "allowed_values": [0.5, 1.0, 1.5, 2.0]
}
```
Только эти дробные числа разрешены

```json
{
  "allowed_values": ["red", "green", "blue", "yellow"]
}
```
Только эти строки разрешены

**Использование:**
```python
# Приоритет задачи (только определенные значения)
obj.setProperty("priority", 3)  # OK: 3 в списке
obj.setProperty("priority", 4)  # ValueError: not in allowed values

# Предустановленные цвета RGB лампы
obj.setProperty("color", "blue")  # OK
obj.setProperty("color", "pink")  # ValueError: not in allowed values
```

**Комбинация с другими параметрами:**
```json
{
  "min": 0,
  "max": 100,
  "step": 10,
  "allowed_values": [10, 20, 30, 50, 100]
}
```
Значения должны соответствовать И step, И allowed_values

### rate_limit (Ограничение частоты изменений)

**Применимо к:** всем типам  
**Тип:** `float` (секунды)  
**Описание:** Минимальный интервал времени между изменениями свойства в секундах. Защищает от дребезга и частых изменений.

**Пример:**
```json
{
  "rate_limit": 5.0
}
```
Свойство можно изменить не чаще раза в 5 секунд

**Использование:**
```python
# Кнопка с защитой от дребезга
obj.setProperty("button", True)   # OK: первое нажатие
time.sleep(1)
obj.setProperty("button", True)   # ValueError: слишком быстро
time.sleep(5)
obj.setProperty("button", True)   # OK: прошло достаточно времени

# Обход rate_limit для системных операций
prop_manager.setValue(True, bypass_rate_limit=True)  # OK
```

**Ошибка rate_limit содержит информацию о времени ожидания:**
```
ValueError: Property 'button' can be changed only once per 5.0 seconds. 
Please wait 3.2 more seconds.
```

### depends_on (Зависимости между свойствами)

**Применимо к:** всем типам  
**Тип:** `dict` или `list` of `dict`  
**Описание:** Определяет зависимости свойства от значений других свойств. Позволяет устанавливать значение только при выполнении условий.

**Формат зависимости:**
```json
{
  "property": "имя_свойства",
  "value": "ожидаемое_значение",
  "condition": "equals|not_equals|greater_than|less_than|greater_or_equal|less_or_equal|in|not_in",
  "error_message": "Пользовательское сообщение об ошибке (опционально)"
}
```

**Условия (condition):**
- `equals` (по умолчанию) - равно
- `not_equals` - не равно
- `greater_than` - больше
- `less_than` - меньше
- `greater_or_equal` - больше или равно
- `less_or_equal` - меньше или равно
- `in` - входит в список (value должен быть list)
- `not_in` - не входит в список (value должен быть list)

**Примеры:**

**1. Простая зависимость (equals):**
```json
{
  "depends_on": {
    "property": "enabled",
    "value": true,
    "condition": "equals"
  }
}
```

**2. Зависимость с условием больше:**
```json
{
  "depends_on": {
    "property": "temperature",
    "value": 25.0,
    "condition": "greater_than",
    "error_message": "Вентилятор можно включить только при температуре выше 25°C"
  }
}
```

**3. Множественные зависимости (все должны быть выполнены):**
```json
{
  "depends_on": [
    {
      "property": "enabled",
      "value": true,
      "condition": "equals"
    },
    {
      "property": "mode",
      "value": "manual",
      "condition": "equals"
    }
  ]
}
```

**4. Зависимость с проверкой вхождения в список:**
```json
{
  "depends_on": {
    "property": "mode",
    "value": ["manual", "auto"],
    "condition": "in"
  }
}
```

**Использование:**
```python
# Мощность обогревателя зависит от режима
obj.setProperty("mode", "auto")
try:
    obj.setProperty("power", 1500)  # Ошибка: режим должен быть "manual"
except ValueError as e:
    print(e)  # "Мощность можно изменять только в ручном режиме"

obj.setProperty("mode", "manual")
obj.setProperty("power", 1500)  # OK

# Вентилятор зависит от температуры
obj.setProperty("temperature", 22.0)
try:
    obj.setProperty("fan_speed", 50)  # Ошибка: температура < 25
except ValueError as e:
    print(e)  # "Вентилятор можно включить только при температуре выше 25°C"

obj.setProperty("temperature", 28.0)
obj.setProperty("fan_speed", 50)  # OK
```

## Примеры использования

### Пример 1: Температура с валидацией

```json
{
  "min": -50.0,
  "max": 150.0,
  "decimals": 1,
  "default_value": "20.0",
  "icon": "fas fa-thermometer-half",
  "color": "#FF5722",
  "sort_order": 1
}
```

**Использование:**
```python
# Установка значения
obj.setProperty("temperature", "25.5")  # OK
obj.setProperty("temperature", "200")   # Ошибка: больше max

# Получение
temp = obj.getProperty("temperature")  # 25.5
icon = obj.getProperty("temperature", data="icon")  # "fas fa-thermometer-half"
```

### Пример 2: Счетчик с ограничениями

```json
{
  "min": 0,
  "max": 9999,
  "default_value": "0",
  "icon": "fas fa-counter",
  "color": "#2196F3",
  "sort_order": 2
}
```

### Пример 3: Статус устройства (enum)

```json
{
  "enum_values": {
    "0": "Выключено",
    "1": "Включено",
    "2": "Ошибка",
    "3": "Обслуживание"
  },
  "icon": "fas fa-power-off",
  "color": "#4CAF50",
  "default_value": "0",
  "sort_order": 0
}
```

**Использование:**
```python
# Установка
obj.setProperty("status", "1")

# Получение значения
status = obj.getProperty("status")  # "1"

# Получение описания
status_text = obj.getProperty("status", data="text")  # "Включено"

# Получение иконки
icon = obj.getProperty("status", data="icon")  # "fas fa-power-off"
```

### Пример 4: Email с валидацией

```json
{
  "regexp": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
  "default_value": "",
  "icon": "fas fa-envelope",
  "color": "#009688",
  "sort_order": 5
}
```

### Пример 5: Read-only системное свойство

```json
{
  "read_only": true,
  "default_value": "1.0.0",
  "icon": "fas fa-code-branch",
  "color": "#607D8B",
  "sort_order": 100
}
```

**Использование:**
```python
# Попытка изменить
try:
    obj.setProperty("version", "2.0.0")
except PermissionError as e:
    print(e)  # "Property 'version' is read-only and cannot be modified"
```

### Пример 6: Яркость светодиода с дискретностью

```json
{
  "min": 0,
  "max": 100,
  "step": 10,
  "default_value": "50",
  "icon": "fas fa-lightbulb",
  "color": "#FFC107",
  "sort_order": 1
}
```

**Использование:**
```python
obj.setProperty("brightness", 50)  # OK: кратно 10
obj.setProperty("brightness", 37)  # ValueError: not aligned with step 10
```

### Пример 7: Температура термостата с дискретностью и зависимостью

```json
{
  "min": 18.0,
  "max": 30.0,
  "step": 0.5,
  "decimals": 1,
  "depends_on": {
    "property": "enabled",
    "value": true,
    "condition": "equals",
    "error_message": "Температуру можно изменять только если термостат включен"
  },
  "icon": "fas fa-thermometer-half",
  "color": "#FF5722",
  "sort_order": 2
}
```

### Пример 8: Приоритет задачи с разрешенными значениями

```json
{
  "allowed_values": [1, 2, 3, 5, 10],
  "default_value": "2",
  "icon": "fas fa-flag",
  "color": "#FF9800",
  "sort_order": 3
}
```

**Использование:**
```python
obj.setProperty("priority", 3)  # OK: в списке allowed_values
obj.setProperty("priority", 4)  # ValueError: not in allowed values
```

### Пример 9: Кнопка с защитой от дребезга

```json
{
  "rate_limit": 2.0,
  "icon": "fas fa-hand-pointer",
  "color": "#2196F3",
  "sort_order": 4
}
```

**Использование:**
```python
obj.setProperty("button", True)   # OK
time.sleep(1)
obj.setProperty("button", True)   # ValueError: can be changed only once per 2.0 seconds
time.sleep(2)
obj.setProperty("button", True)   # OK
```

### Пример 10: Комбинация всех расширенных валидаций

```json
{
  "min": 18.0,
  "max": 25.0,
  "step": 0.5,
  "decimals": 1,
  "allowed_values": [18.0, 18.5, 19.0, 19.5, 20.0, 20.5, 21.0, 21.5, 22.0, 22.5, 23.0, 23.5, 24.0, 24.5, 25.0],
  "rate_limit": 10.0,
  "depends_on": {
    "property": "enabled",
    "value": true,
    "condition": "equals"
  },
  "default_value": "22.0",
  "icon": "fas fa-temperature-high",
  "color": "#FF5722",
  "sort_order": 1
}
```

**Описание:**
- Диапазон: 18-25°C
- Дискретность: 0.5°C
- Только определенные значения из списка
- Не чаще раза в 10 секунд
- Только если термостат включен

## API Response

При получении свойства через API, в ответе будут включены все параметры:

**Базовый пример:**
```json
{
  "name": "temperature",
  "type": "float",
  "value": 25.5,
  "icon": "fas fa-thermometer-half",
  "color": "#FF5722",
  "sort_order": 1,
  "min": -50.0,
  "max": 150.0,
  "decimals": 1,
  "read_only": false
}
```

**С расширенными валидациями:**
```json
{
  "name": "target_temp",
  "type": "float",
  "value": 22.0,
  "icon": "fas fa-temperature-high",
  "color": "#FF5722",
  "sort_order": 1,
  "min": 18.0,
  "max": 30.0,
  "decimals": 1,
  "step": 0.5,
  "allowed_values": [18.0, 18.5, 19.0, 19.5, 20.0, 20.5, 21.0, 21.5, 22.0],
  "rate_limit": 10.0,
  "depends_on": {
    "property": "enabled",
    "value": true,
    "condition": "equals"
  },
  "read_only": false
}
```

**Для enum типа:**
```json
{
  "name": "status",
  "type": "enum",
  "value": "1",
  "text": "Включено",
  "enum_values": {
    "0": "Выключено",
    "1": "Включено",
    "2": "Ошибка"
  },
  "icon": "fas fa-power-off",
  "color": "#4CAF50",
  "sort_order": 0,
  "read_only": false
}
```

## Валидация

Валидация выполняется автоматически при вызове `setProperty()` или присвоении значения через `obj.property = value`.

При нарушении правил валидации выбрасывается исключение `ValueError` (или `PermissionError` для read_only) с описанием ошибки:

**Примеры ошибок валидации:**

```python
# Базовая валидация
try:
    obj.setProperty("temperature", "200")
except ValueError as e:
    print(e)  # "Value 200.0 is greater than maximum 150.0"

# Step валидация
try:
    obj.setProperty("brightness", "37")
except ValueError as e:
    print(e)  # "Value 37 is not aligned with step 10 (base: 0). Allowed values: 0, 10, 20..."

# Allowed values валидация
try:
    obj.setProperty("priority", "4")
except ValueError as e:
    print(e)  # "Value 4 is not in allowed values: [1, 2, 3, 5, 10]"

# Rate limit валидация
try:
    obj.setProperty("button", True)
    time.sleep(1)
    obj.setProperty("button", True)
except ValueError as e:
    print(e)  # "Property 'button' can be changed only once per 5.0 seconds. Please wait 3.2 more seconds."

# Depends on валидация
try:
    obj.setProperty("mode", "auto")
    obj.setProperty("power", 1500)
except ValueError as e:
    print(e)  # "Cannot set 'power' to '1500': depends on 'mode' equals 'manual', but current value is 'auto'"
    # или с custom error_message: "Мощность можно изменять только в ручном режиме"

# Read-only защита
try:
    obj.setProperty("version", "2.0.0")
except PermissionError as e:
    print(e)  # "Property 'version' is read-only and cannot be modified"
```

**Порядок валидации:**

1. Проверка `read_only`
2. Проверка `rate_limit`
3. Проверка типа и преобразование значения
4. Проверка `min`/`max`
5. Проверка `step` (для int/float)
6. Проверка `decimals` (для float)
7. Проверка `regexp` (для str)
8. Проверка `enum_values` (для enum)
9. Проверка `allowed_values` (для всех типов кроме enum)
10. Проверка `depends_on` (в ObjectManager.setProperty)

**Отключение валидации при загрузке из БД:**

При загрузке значений из базы данных (`init=True`), проверки `min`/`max`, `step`, `regexp`, `enum_values` и `allowed_values` отключены. Это позволяет загружать старые значения, которые могли быть сохранены до изменения правил валидации.

```python
# При загрузке из БД валидация не применяется
value = prop_manager._decodeValue("150", init=True)  # OK, даже если max=100

# При установке нового значения валидация применяется
prop_manager.setValue("150")  # ValueError: greater than maximum
```

## Рекомендации

### Общие рекомендации
1. **sort_order**: Используйте интервалы (0, 10, 20, ...) для возможности вставки новых свойств между существующими
2. **decimals**: Для температуры обычно достаточно 1-2 знаков, для точных измерений - 3-4
3. **regexp**: Тестируйте регулярные выражения перед сохранением
4. **read_only**: Используйте для системных свойств и метаданных
5. **default_value**: Устанавливайте разумные значения по умолчанию для улучшения UX
6. **icon**: Используйте иконки FontAwesome для единообразия интерфейса
7. **color**: Используйте цвета для быстрой визуальной идентификации типа свойства

### Рекомендации для расширенных валидаций

#### step (Дискретность)
- ✅ Используйте для пользовательских интерфейсов (слайдеры, регуляторы)
- ✅ Подходит для IoT устройств с фиксированными шагами изменения
- ⚠️ Учитывайте погрешность для float (используется 1e-9)
- 💡 Примеры: яркость света (шаг 10%), температура (шаг 0.5°C), громкость (шаг 5)

#### allowed_values
- ✅ Используйте вместо enum, если нужны значения не-строковых типов
- ✅ Подходит для ограниченного набора допустимых значений
- ⚠️ Не используйте одновременно с enum_values (для enum используйте только enum_values)
- 💡 Примеры: приоритеты [1,2,3,5], предустановленные цвета ["red","green","blue"]

#### rate_limit
- ✅ Защита от дребезга кнопок (1-3 секунды)
- ✅ Ограничение частоты обновления датчиков (5-60 секунд)
- ✅ Защита от чрезмерной нагрузки на систему
- ⚠️ Используйте bypass_rate_limit=True для системных операций
- 💡 Примеры: кнопка звонка (2 сек), датчик движения (5 сек), настройки (10 сек)

#### depends_on
- ✅ Обеспечивает логическую связность между свойствами
- ✅ Предотвращает некорректные состояния системы
- ⚠️ Избегайте циклических зависимостей
- ⚠️ Используйте информативные error_message для лучшего UX
- 💡 Примеры: мощность зависит от режима, вентилятор от температуры, яркость от включенности

### Комбинации валидаций

**Хорошие комбинации:**
- `min` + `max` + `step` - полный контроль числовых значений
- `step` + `allowed_values` - дискретность + дополнительное ограничение
- `depends_on` + `rate_limit` - логическая связь + защита от частых изменений
- `min` + `max` + `depends_on` - диапазон + условие активации

**Избегайте:**
- `allowed_values` для enum типов (используйте `enum_values`)
- Слишком строгие комбинации, которые делают свойство непригодным для использования
- Циклические зависимости в `depends_on`

## Структура JSON в базе данных

Все параметры хранятся в одном JSON объекте в поле `params`:

**Для типов int/float/str (базовые параметры):**
```json
{
  "min": 0,
  "max": 100,
  "decimals": 2,
  "regexp": "^[A-Z]+$",
  "icon": "fas fa-icon",
  "color": "#FF5722",
  "sort_order": 10,
  "default_value": "50",
  "read_only": false
}
```

**Для типов int/float/str (с расширенными валидациями):**
```json
{
  "min": 0,
  "max": 100,
  "step": 10,
  "allowed_values": [10, 20, 30, 50, 100],
  "rate_limit": 5.0,
  "depends_on": {
    "property": "enabled",
    "value": true,
    "condition": "equals",
    "error_message": "Можно изменять только если включено"
  },
  "decimals": 2,
  "icon": "fas fa-icon",
  "color": "#FF5722",
  "sort_order": 10,
  "default_value": "50",
  "read_only": false
}
```

**Для типа enum:**
```json
{
  "enum_values": {
    "0": "Value 1",
    "1": "Value 2",
    "icon": "Icon Value",
    "color": "Color Value"
  },
  "icon": "fas fa-icon",
  "color": "#FF5722",
  "sort_order": 10,
  "default_value": "0",
  "read_only": false,
  "rate_limit": 2.0,
  "depends_on": {
    "property": "mode",
    "value": "manual",
    "condition": "equals"
  }
}
```

> 💡 **Важное отличие:** Для enum типа все значения перечисления хранятся в отдельном объекте `enum_values`, что позволяет использовать любые ключи, включая системные (`icon`, `color` и т.д.) как значения enum без конфликтов.

**Системные ключи:**

*Общие параметры (для всех типов):*
- `icon` - иконка для отображения
- `color` - цвет для отображения
- `sort_order` - порядок сортировки
- `default_value` - значение по умолчанию
- `read_only` - защита от изменения

*Базовые параметры валидации:*
- `min`, `max` - диапазон значений (int, float)
- `decimals` - количество знаков после запятой (float)
- `regexp` - регулярное выражение (str)
- `enum_values` - значения перечисления (enum)

*Расширенные параметры валидации:*
- `step` - дискретность значений (int, float)
- `allowed_values` - список разрешенных значений (все типы кроме enum)
- `rate_limit` - минимальный интервал между изменениями в секундах (все типы)
- `depends_on` - зависимости от других свойств (все типы)
