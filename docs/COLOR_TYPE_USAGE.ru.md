# Использование типа свойства `color`

Тип `color` предназначен для RGB-ламп, LED-лент, Zigbee/MQTT-устройств с цветом и любых интеграций, где нужно хранить и конвертировать цвет между форматами (RGB, HEX, XY, HS, HSV и т.д.).

В интерфейсе редактирования свойства (модуль **Objects**) для типа `color` доступен блок **«Параметры типа color»**:

| Поле в UI | Ключ в `params` | По умолчанию |
|-----------|-----------------|--------------|
| Формат чтения | `read_format` | `canonical` |
| Формат записи | `write_format` | `auto` |
| Единица цветовой температуры | `color_temp_unit` | `kelvin` |
| Шкала hue | `hue_scale` | `360` |
| Шкала saturation | `sat_scale` | `100` |

> Подробнее о других параметрах свойств (icon, history, rate_limit…) см. [PARAMS_DOCUMENTATION.md](PARAMS_DOCUMENTATION.md).

---

## Как устроено хранение

Внутри системы цвет хранится в **универсальном формате** (JSON в БД):

```json
{
  "rgb": [84, 124, 255],
  "xy": [0.192685, 0.156741],
  "Y": 23.52
}
```

- `rgb` — цвет в sRGB (0–255)
- `xy` — координаты CIE 1931 (хроматичность)
- `Y` — яркость (luminance), нужна для корректного пересчёта XY ↔ RGB

При записи любого поддерживаемого формата значение нормализуется в этот вид. При чтении — преобразуется в `read_format`.

---

## `read_format` — формат чтения

Определяет, **в каком виде** свойство отдаёт значение через:

- `obj.getProperty("color")` / `getValue()`
- `getProperty("Object.color", data="hex")` — явный формат (перекрывает `read_format`)
- `getHistory()` — **все** записи истории в том же формате
- MCP `osys_get_property`, API `/api/properties/history`

### Доступные значения

| `read_format` | Пример ответа | Когда использовать |
|---------------|---------------|-------------------|
| `canonical` | `{"rgb":[...],"xy":[...],"Y":...}` | Отладка, универсальные сценарии |
| `hex` | `"#547CFF"` | UI, простые интеграции |
| `rgb` | `{"r":84,"g":124,"b":255}` | REST/MQTT с RGB |
| `xy` | `{"x":0.19,"y":0.16}` | Zigbee2MQTT, лампы с XY-управлением |
| `hs` | `{"hue":226,"saturation":67}` | Hue/Saturation (2 канала) |
| `hsv` | `{"hsv":"0,90,78"}` | HSV-устройства |
| `hsl` | `{"hsl":"120,80,90"}` | HSL |
| `hsb` | `{"hsb":"360,100,100"}` | HSB (эквивалент HSV в модели) |
| `color_temp` | `4000` или mired | Белые/тёплые лампы (см. `color_temp_unit`) |
| `zigbee2mqtt` | `{"color":{"x":...,"y":...}}` | Прямая пересылка в Z2M |

**Пример настройки для RGB-лампы с HEX в UI:**

```json
{
  "read_format": "hex",
  "write_format": "auto"
}
```

**Пример для Zigbee-лампы с XY (как на скриншоте):**

```json
{
  "read_format": "xy",
  "write_format": "auto",
  "hue_scale": 360,
  "sat_scale": 100,
  "color_temp_unit": "kelvin"
}
```

---

## `write_format` — формат записи

| Значение | Поведение |
|----------|-----------|
| `auto` | Формат входа определяется автоматически (рекомендуется) |
| `hex`, `rgb`, `xy`, `hs`, … | **Строгий режим**: вход должен соответствовать формату, иначе `ValueError` |

`auto` принимает:

- английские имена: `red`, `green`, `blue`, `warmwhite`, `orange`…
- HEX: `#547CFF` или `547CFF`
- RGB-строка: `46,102,150`
- dict: `{"r":46,"g":102,"b":150}`
- XY: `{"x":0.3,"y":0.6}`
- Zigbee2MQTT: `{"color":{"x":0.123,"y":0.456}}`
- HSV/HSB/HSL: `{"hsv":"0,90,78"}` или `{"color":{"hue":360,"saturation":100}}`
- canonical JSON: `{"rgb":[84,102,150]}`

Подробный список имён — в разделе [Имена цветов](#имена-цветов-запись-по-имени) ниже.

**Строгий режим** полезен, когда плагин всегда шлёт, например, только HEX:

```json
{
  "read_format": "hex",
  "write_format": "hex"
}
```

```python
obj.setProperty("Lamp.color", "#FF0000")   # OK
obj.setProperty("Lamp.color", {"x":0.1,"y":0.2})  # ValueError
```

---

## Имена цветов (запись по имени)

При `write_format: auto` строка вроде `"red"` или `"relax"` воспринимается как **имя цвета**, если оно есть в списке ниже. Имена только на **английском** (регистр не важен). Локализованные названия (`красный`, `тёплый белый`) не поддерживаются — используйте HEX, RGB или XY.

```python
setProperty("Lamp.color", "red", source="Scenario")
setProperty("Lamp.color", "softwhite", source="Scenario")
setProperty("Lamp.color", "relax", source="Scenario")
```

Несколько имён могут указывать на один RGB (алиасы). Значения HTML/CSS совпадают со [стандартными именами CSS](https://www.w3.org/TR/css-color-4/#named-colors) / [HTML color names](https://htmlcolorcodes.com/color-names/). Источник истины в коде — `COLOR_NAME_MAP` в `app/core/lib/converters/color.py`.

### HTML / CSS (140 стандартных ключевых слов)

| Группа | Имена |
|--------|-------|
| Красные | `indianred`, `lightcoral`, `salmon`, `darksalmon`, `lightsalmon`, `crimson`, `red`, `firebrick`, `darkred` |
| Розовые | `pink`, `lightpink`, `hotpink`, `deeppink`, `mediumvioletred`, `palevioletred` |
| Оранжевые | `coral`, `tomato`, `orangered`, `darkorange`, `orange` |
| Жёлтые | `gold`, `yellow`, `lightyellow`, `lemonchiffon`, `lightgoldenrodyellow`, `papayawhip`, `moccasin`, `peachpuff`, `palegoldenrod`, `khaki`, `darkkhaki` |
| Фиолетовые | `lavender`, `thistle`, `plum`, `violet`, `orchid`, `fuchsia`, `magenta`, `mediumorchid`, `mediumpurple`, `rebeccapurple`, `blueviolet`, `darkviolet`, `darkorchid`, `darkmagenta`, `purple`, `indigo`, `slateblue`, `darkslateblue`, `mediumslateblue` |
| Зелёные | `greenyellow`, `chartreuse`, `lawngreen`, `lime`, `limegreen`, `palegreen`, `lightgreen`, `mediumspringgreen`, `springgreen`, `mediumseagreen`, `seagreen`, `forestgreen`, `green`, `darkgreen`, `yellowgreen`, `olivedrab`, `olive`, `darkolivegreen`, `mediumaquamarine`, `darkseagreen`, `lightseagreen`, `darkcyan`, `teal` |
| Синие | `aqua`, `cyan`, `lightcyan`, `paleturquoise`, `aquamarine`, `turquoise`, `mediumturquoise`, `darkturquoise`, `cadetblue`, `steelblue`, `lightsteelblue`, `powderblue`, `lightblue`, `skyblue`, `lightskyblue`, `deepskyblue`, `dodgerblue`, `cornflowerblue`, `royalblue`, `blue`, `mediumblue`, `darkblue`, `navy`, `midnightblue` |
| Коричневые | `cornsilk`, `blanchedalmond`, `bisque`, `navajowhite`, `wheat`, `burlywood`, `tan`, `rosybrown`, `sandybrown`, `goldenrod`, `darkgoldenrod`, `peru`, `chocolate`, `saddlebrown`, `sienna`, `brown`, `maroon` |
| Белые | `white`, `snow`, `honeydew`, `mintcream`, `azure`, `aliceblue`, `ghostwhite`, `whitesmoke`, `seashell`, `beige`, `oldlace`, `floralwhite`, `ivory`, `antiquewhite`, `linen`, `lavenderblush`, `mistyrose` |
| Серые | `gainsboro`, `lightgray`, `lightgrey`, `silver`, `darkgray`, `darkgrey`, `gray`, `grey`, `dimgray`, `dimgrey`, `lightslategray`, `lightslategrey`, `slategray`, `slategrey`, `darkslategray`, `darkslategrey`, `black` |

Дополнительно (не из CSS): `mint`.

### Smart-home: CCT-белые и сцены

RGB вычисляется из цветовой температуры через `kelvin_to_rgb()` (та же функция, что для формата `color_temp`).

| Имя | ~K | RGB |
|-----|-----|-----|
| `bedtime` | 1800 | 255, 126, 0 |
| `candlelight`, `candle`, `nightlight` | 2000 | 255, 137, 14 |
| `relax` | 2200 | 255, 146, 39 |
| `softwhite`, `incandescent` | 2700 | 255, 167, 87 |
| `neutralwhite`, `naturalwhite`, `reading` | 4000 | 255, 206, 166 |
| `brightwhite` | 5000 | 255, 228, 206 |
| `energize` | 6500 | 255, 254, 250 |
| `arcticwhite`, `coldwhite` | 7500 | 230, 235, 255 |

### Smart-home: legacy-белые

Фиксированные RGB для обратной совместимости (могут отличаться от CCT-имён выше):

| Имя | RGB |
|-----|-----|
| `warmwhite` | 255, 244, 229 |
| `coolwhite` | 229, 244, 255 |
| `daylight` | 255, 255, 251 |
| `offwhite` | 253, 245, 230 |

### Smart-home: атмосфера

| Имя | RGB | Назначение |
|-----|-----|------------|
| `sunset` | 255, 120, 60 | Тёплый вечерний свет |
| `amber` | 255, 191, 0 | Ночная навигация, тёплый акцент |
| `fire` | 255, 80, 20 | Эффект камина / свечи |

> Точные значения в Кельвинах (`2700`, `4000`…) задавайте форматом `color_temp` (`read_format` / `write_format` = `color_temp`), а не именами цветов.

---

## `hue_scale` и `sat_scale`

Некоторые протоколы (Zigbee, отдельные прошивки) используют **шкалу 0–254** вместо стандартных 0–360° (hue) и 0–100% (saturation).

| Параметр | Стандарт | Zigbee-подобные устройства |
|----------|----------|---------------------------|
| `hue_scale` | `360` | `254` (или как в документации устройства) |
| `sat_scale` | `100` | `254` |

Система нормализует hue/sat при **записи** и денормализует при **чтении** в `read_format: hs` / `hsv` / `hsl` / `hsb`.

Если лампа отдаёт `hue: 127` при шкале 254 — укажите `hue_scale: 254`, и в сценариях вы получите согласованные значения.

---

## `color_temp_unit`

Используется только при `read_format` / `write_format` = `color_temp`:

| Значение | Описание |
|----------|----------|
| `kelvin` | Температура в Кельвинах (2700, 4000, 6500…) |
| `mired` | Micro reciprocal degree (типично для Zigbee: `mired = 1_000_000 / kelvin`) |

---

## Работа из кода и сценариев

### Чтение

```python
# В формате read_format свойства (например xy)
color = obj.getProperty("Rgb01.color")

# Явный формат (не зависит от read_format)
hex_color = obj.getProperty("Rgb01.color", "hex")
xy_color = obj.getProperty("Rgb01.color", "xy")

# Через PropertyManager (в методах объекта)
color = self.getProperty("color")  # read_format
```

### Запись

```python
from app.core.lib.object import setProperty

setProperty("Rgb01.color", "red", source="Scenario")
setProperty("Rgb01.color", "#547CFF", source="Scenario")
setProperty("Rgb01.color", {"color": {"x": 0.3, "y": 0.6}}, source="Zigbee")
```

### История

```python
history = obj.getHistory("color", limit=10, order_desc=True)
for item in history:
    print(item["added"], item["value"])  # value всегда в read_format
```

Для графиков и агрегатов (`min`/`max`/`avg`) тип `color` не подходит — используйте `count` или отдельные числовые свойства (яркость, color_temp).

---

## Zigbee2MQTT: типичные payload

Ниже — форматы, которые `write_format: auto` понимает из коробки (обёртка `{"color": {...}}`).

### XY (CIE 1931)

```json
{"color": {"x": 0.123, "y": 0.456}}
```

Альтернативы через RGB:

```json
{"color": {"r": 46, "g": 102, "b": 150}}
{"color": {"rgb": "46,102,150"}}
{"color": {"hex": "#547CFF"}}
```

Рекомендуемые params:

```json
{"read_format": "xy", "write_format": "auto"}
```

### Hue / Saturation

```json
{"color": {"hue": 360, "saturation": 100}}
```

Через HSB / HSV / HSL:

```json
{"color": {"h": 360, "s": 100, "b": 100}}
{"color": {"hsv": "360,100,100"}}
{"color": {"hsl": "360,100,100"}}
```

Рекомендуемые params:

```json
{"read_format": "hs", "write_format": "auto", "hue_scale": 360, "sat_scale": 100}
```

или для HSV-ответа:

```json
{"read_format": "hsv", "write_format": "auto"}
```

---

## Рекомендуемые конфигурации

### Универсальная RGB-лампа (UI, сценарии)

```json
{
  "icon": "mdi:palette",
  "read_format": "hex",
  "write_format": "auto"
}
```

### Zigbee RGBW — отдельные свойства

| Свойство | `read_format` | Назначение |
|----------|---------------|------------|
| `color` | `hex` | Отображение в UI |
| `color_xy` | `xy` | Команды Z2M по XY |
| `color_hsv` | `hsv` | Команды Z2M по HSV |
| `brightness` | `int` | Яркость (отдельное свойство) |

### Плагин / linked property

В `write_format` оставляйте `auto`, если плагин может присылать разные форматы с устройства. В `read_format` укажите формат, удобный для **вашего** плагина при отправке команд обратно на устройство.

---

## Частые ошибки

| Симптом | Причина | Решение |
|---------|---------|---------|
| `Color write format mismatch` | `write_format` строгий, формат входа другой | Поставить `auto` или сменить вход |
| `Unknown color name` | Неизвестное имя цвета | Использовать HEX/RGB или имя из раздела [Имена цветов](#имена-цветов-запись-по-имени) / `COLOR_NAME_MAP` |
| XY «плывёт» после записи | Roundtrip RGB↔XY без сохранения Y | При частичном обновлении XY яркость берётся из текущего значения (это нормально) |
| История в разных форматах | Старая версия ядра | Обновить osysHome; история должна быть в `read_format` |

---

## См. также

- [PARAMS_DOCUMENTATION.md](PARAMS_DOCUMENTATION.md) — общие параметры свойств
- [binding.ru.md](binding.ru.md) — связывание с плагинами
- [automation.ru.md](automation.ru.md) — сценарии и `setProperty`
- [COLOR_TYPE_USAGE.md](COLOR_TYPE_USAGE.md) — English version
- Карта имён: `app/core/lib/converters/color.py` (`COLOR_NAME_MAP`)
- Тесты: `tests/test_color_value.py`, `tests/test_object_manager.py`
