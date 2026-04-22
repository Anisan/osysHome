# Разработка плагинов

В этом разделе описано, как создать собственный плагин для osysHome — от минимальной структуры до полнофункционального плагина с настройками, фоновой задачей и веб-интерфейсом.

---

## Структура плагина

Каждый плагин — это папка в `plugins/` со следующей структурой:

```
plugins/MyPlugin/
├── __init__.py           ← обязательно: главный класс плагина
├── requirements.txt      ← (опционально) зависимости Python
├── templates/
│   └── my_plugin.html    ← шаблон страницы настроек (Jinja2)
├── static/
│   └── MyPlugin.png      ← иконка плагина (желательно 64x64 PNG)
├── translations/
│   ├── en.json           ← переводы на английский
│   └── ru.json           ← переводы на русский
└── docs/
    └── README.md         ← документация плагина
```

> Имя папки и имя класса в `__init__.py` **должны совпадать**.

---

## Минимальный плагин

Создайте файл `plugins/MyPlugin/__init__.py`:

```python
from app.core.main.BasePlugin import BasePlugin


class MyPlugin(BasePlugin):

    def __init__(self, app):
        super().__init__(app, __name__)
        self.title = "My Plugin"
        self.description = "Описание моего плагина"
        self.category = "App"      # App, Devices, System
        self.version = "0.1"
        self.actions = []          # список поддерживаемых действий

    def initialization(self):
        self.logger.info("MyPlugin инициализирован")

    def admin(self, request):
        return self.render("my_plugin.html", {})
```

Создайте шаблон `plugins/MyPlugin/templates/my_plugin.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>My Plugin</h2>
<p>Мой первый плагин работает!</p>
{% endblock %}
```

После перезапуска системы плагин появится в **Admin → Modules** и будет доступен по адресу `/admin/MyPlugin`.

---

> Примечание: в текущем ядре предпочтительнее передавать явное имя плагина в конструктор (`super().__init__(app, "MyPlugin")`) и использовать `layouts/module_admin.html` как базовый admin-шаблон.
> Также `BasePlugin` предоставляет два встроенных маршрута: `/admin/<PluginName>` и `/page/<PluginName>`.

## Базовый класс BasePlugin

`BasePlugin` предоставляет всю базовую инфраструктуру. При вызове `super().__init__(app, __name__)` происходит:

- Регистрация Flask Blueprint с маршрутами плагина
- Загрузка конфигурации из БД (`self.config`)
- Инициализация логгера (`self.logger`)
- Подключение статических файлов и шаблонов

### Атрибуты

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `self.name` | `str` | Имя плагина (из имени папки) |
| `self.title` | `str` | Отображаемое название |
| `self.description` | `str` | Описание плагина |
| `self.category` | `str` | Категория: `App`, `Devices`, `System` |
| `self.version` | `str` | Версия |
| `self.system` | `bool` | Системный плагин (скрыть из общего списка) |
| `self.actions` | `list` | Список поддерживаемых действий |
| `self.config` | `dict` | Конфигурация, загруженная из БД |
| `self.logger` | `Logger` | Логгер плагина |

---

## Действия (Actions)

Объявите в `self.actions` те действия, которые ваш плагин поддерживает.

### `cycle` — фоновая задача

```python
self.actions = ['cycle']

def cyclic_task(self):
    """Вызывается в цикле в отдельном потоке."""
    import time
    # Сделать что-то
    self.logger.debug("Выполняется цикл")
    time.sleep(10)  # пауза между итерациями
```

> **Важно:** `cyclic_task` выполняется в бесконечном цикле. Обязательно добавляйте `time.sleep()`, чтобы не нагружать CPU.

### `proxy` — отслеживание изменений свойств

```python
self.actions = ['proxy']

def changeProperty(self, obj, prop, value):
    """Вызывается при каждом изменении любого свойства в системе."""
    if obj == "MotionSensor" and prop == "occupancy" and value:
        self.logger.info("Обнаружено движение!")
        # Включить свет
        from app.core.lib.object import setProperty
        setProperty("HallLamp.state", True)
```

### `say` — вывод речи/уведомлений

```python
self.actions = ['say']

def say(self, message: str, level: int = 0, args=None):
    """Вызывается когда система хочет что-то «сказать»."""
    self.logger.info(f"[TTS] {message}")
    # Синтезировать и воспроизвести речь
    self._synthesize_and_play(message)
```

### `playsound` — воспроизведение звука

```python
self.actions = ['playsound']

def playSound(self, file_name: str, level: int = 0):
    """Воспроизвести звуковой файл."""
    import subprocess
    subprocess.Popen(["aplay", file_name])
```

### `widget` — виджет на Dashboard

```python
self.actions = ['widget']

def widget(self, name):
    """Вернуть HTML-код виджета для Dashboard."""
    data = {"temperature": getProperty("HomeSensor.temperature")}
    return self.render("widget.html", data)
```

### `search` — глобальный поиск

```python
self.actions = ['search']

def search(self, query: str) -> list:
    """Вернуть результаты поиска по запросу."""
    results = []
    # Поиск в данных плагина
    if query.lower() in "my device":
        results.append({
            "title": "My Device",
            "description": "Найдено в MyPlugin",
            "url": "/admin/MyPlugin"
        })
    return results
```

---

## Конфигурация плагина

Конфигурация плагина хранится в базе данных в формате JSON. Используйте `self.config` для чтения и сохранения настроек.

```python
def initialization(self):
    # Читаем настройки (с дефолтными значениями)
    host = self.config.get("host", "localhost")
    port = self.config.get("port", 1883)
    self.logger.info(f"Подключаюсь к {host}:{port}")

def admin(self, request):
    if request.method == "POST":
        # Сохраняем настройки
        self.config["host"] = request.form.get("host", "localhost")
        self.config["port"] = int(request.form.get("port", 1883))
        self.saveConfig()
        return redirect(f"/admin/{self.name}")
    
    return self.render("my_plugin.html", {"config": self.config})
```

В шаблоне:

```html
{% extends "base.html" %}
{% block content %}
<form method="POST">
    <label>Хост:</label>
    <input type="text" name="host" value="{{ config.get('host', 'localhost') }}">
    
    <label>Порт:</label>
    <input type="number" name="port" value="{{ config.get('port', 1883) }}">
    
    <button type="submit">Сохранить</button>
</form>
{% endblock %}
```

---

## Работа с объектами из плагина

```python
from app.core.lib.object import (
    addClass, addObject, addClassProperty,
    getProperty, setProperty, callMethod
)
from app.core.lib.constants import PropertyType

def initialization(self):
    # Создать класс для устройств плагина (если не существует)
    addClass("MyDevice", description="Устройство MyPlugin", update=True)
    
    # Добавить свойство к классу
    addClassProperty(
        name="state",
        class_name="MyDevice",
        description="Состояние устройства",
        type=PropertyType.Boolean,
        history=7  # хранить 7 дней
    )

def cyclic_task(self):
    import time
    # Опросить устройство и обновить значение
    state = self._poll_device()
    setProperty("MyDevice1.state", state)
    time.sleep(5)
```

---

## Регистрация дополнительных маршрутов

Помимо `/admin/<Name>`, можно добавить дополнительные маршруты. Назовите метод с префиксом `route_`:

```python
def route_api(self):
    @self.blueprint.route(f"/api/{self.name}/data", methods=["GET"])
    def get_data():
        from flask import jsonify
        return jsonify({"status": "ok", "data": self._get_data()})

def route_webhook(self):
    @self.blueprint.route(f"/webhook/{self.name}", methods=["POST"])
    def webhook():
        from flask import request, jsonify
        payload = request.json
        self._process_webhook(payload)
        return jsonify({"received": True})
```

---

## Отправка данных на Dashboard (WebSocket)

```python
from app.core.lib.common import sendDataToWebsocket

# Отправить обновление в браузер
sendDataToWebsocket("update", {
    "object": "MyDevice1",
    "property": "state",
    "value": True
})

# Или использовать метод из BasePlugin
self.sendDataToWebsocket("notification", {
    "message": "Устройство подключено",
    "level": "info"
})
```

---

## Переводы

Создайте файлы переводов для интернационализации:

`plugins/MyPlugin/translations/ru.json`:
```json
{
    "MyPlugin": {
        "title": "Мой плагин",
        "settings": "Настройки",
        "host": "Адрес сервера",
        "port": "Порт",
        "save": "Сохранить"
    }
}
```

`plugins/MyPlugin/translations/en.json`:
```json
{
    "MyPlugin": {
        "title": "My Plugin",
        "settings": "Settings",
        "host": "Server address",
        "port": "Port",
        "save": "Save"
    }
}
```

В шаблоне используйте функцию `_()`:

```html
<h2>{{ _('MyPlugin.title') }}</h2>
<label>{{ _('MyPlugin.host') }}:</label>
```

---

## Полный пример: плагин мониторинга HTTP

Плагин, который периодически проверяет доступность URL и обновляет состояние объекта:

```python
import time
import requests
from app.core.main.BasePlugin import BasePlugin
from app.core.lib.object import addClass, addObject, addClassProperty, setProperty
from app.core.lib.constants import PropertyType


class HttpMonitor(BasePlugin):

    def __init__(self, app):
        super().__init__(app, __name__)
        self.title = "HTTP Monitor"
        self.description = "Мониторинг доступности HTTP-ресурсов"
        self.category = "App"
        self.version = "0.1"
        self.actions = ["cycle"]

    def initialization(self):
        # Создать класс для мониторинга
        addClass("HttpEndpoint", description="HTTP-эндпоинт", update=True)
        addClassProperty("online", "HttpEndpoint", type=PropertyType.Boolean)
        addClassProperty("response_time", "HttpEndpoint", type=PropertyType.Float, history=30)
        addClassProperty("url", "HttpEndpoint", type=PropertyType.String)

        # Создать объекты из конфигурации
        for name, url in self.config.get("endpoints", {}).items():
            addObject(name, "HttpEndpoint", update=True)
            setProperty(f"{name}.url", url)

        self.logger.info("HttpMonitor инициализирован")

    def cyclic_task(self):
        for name, url in self.config.get("endpoints", {}).items():
            try:
                start = time.time()
                resp = requests.get(url, timeout=5)
                elapsed = time.time() - start
                setProperty(f"{name}.online", resp.status_code < 400)
                setProperty(f"{name}.response_time", round(elapsed * 1000, 1))
            except Exception:
                setProperty(f"{name}.online", False)
                setProperty(f"{name}.response_time", None)
        
        time.sleep(60)  # проверять раз в минуту

    def admin(self, request):
        if request.method == "POST":
            # Добавить новый эндпоинт
            name = request.form.get("name")
            url = request.form.get("url")
            if name and url:
                endpoints = self.config.get("endpoints", {})
                endpoints[name] = url
                self.config["endpoints"] = endpoints
                self.saveConfig()
                addObject(name, "HttpEndpoint", update=True)
                setProperty(f"{name}.url", url)
        
        endpoints = self.config.get("endpoints", {})
        return self.render("http_monitor.html", {"endpoints": endpoints})
```

---

## Советы и частые ошибки

### Не вызывайте `time.sleep()` слишком долго в `cyclic_task`

Если нужен длинный интервал — используйте меньшее значение sleep с проверкой времени:

```python
def cyclic_task(self):
    import time
    # Делать работу каждые 60 секунд
    self._do_work()
    # Ждём 60 секунд с возможностью прерывания
    for _ in range(60):
        if self.event.is_set():
            break
        time.sleep(1)
```

### Не делайте тяжёлые операции в `changeProperty`

`changeProperty` с `action="proxy"` вызывается на **каждое изменение** в системе. Если там тяжёлый код — это замедлит всю систему. Фильтруйте сразу:

```python
def changeProperty(self, obj, prop, value):
    # Сначала фильтруем — быстро отсекаем ненужные события
    if obj != "MotionSensor":
        return
    if prop != "occupancy":
        return
    # Теперь обрабатываем
    self._handle_motion(value)
```

### Логирование

```python
self.logger.debug("Отладочная информация")    # только при debug=True
self.logger.info("Штатное событие")
self.logger.warning("Предупреждение")
self.logger.error("Ошибка", exc_info=True)   # exc_info=True — добавит трассировку
```

Логи пишутся в `logs/<PluginName>.log`.
