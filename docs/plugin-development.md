# Plugin Development

This section explains how to create a custom osysHome plugin — from the minimal structure to a fully-featured plugin with settings, a background task, and a web interface.

---

## Plugin Structure

Every plugin is a folder inside `plugins/` with the following layout:

```
plugins/MyPlugin/
├── __init__.py           ← required: main plugin class
├── requirements.txt      ← (optional) Python dependencies
├── templates/
│   └── my_plugin.html    ← settings page template (Jinja2)
├── static/
│   └── MyPlugin.png      ← plugin icon (preferably 64×64 PNG)
├── translations/
│   ├── en.json           ← English translations
│   └── ru.json           ← Russian translations
└── docs/
    └── README.md         ← plugin documentation
```

> The folder name and the class name in `__init__.py` **must match**.

---

## Minimal Plugin

Create `plugins/MyPlugin/__init__.py`:

```python
from app.core.main.BasePlugin import BasePlugin


class MyPlugin(BasePlugin):

    def __init__(self, app):
        super().__init__(app, __name__)
        self.title = "My Plugin"
        self.description = "Description of my plugin"
        self.category = "App"      # App, Devices, System
        self.version = "0.1"
        self.actions = []          # list of supported actions

    def initialization(self):
        self.logger.info("MyPlugin initialized")

    def admin(self, request):
        return self.render("my_plugin.html", {})
```

Create the template `plugins/MyPlugin/templates/my_plugin.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>My Plugin</h2>
<p>My first plugin is working!</p>
{% endblock %}
```

After restarting the system, the plugin will appear in **Admin → Modules** and be accessible at `/admin/MyPlugin`.

---

> Note: in current core it is safer to pass explicit plugin name in constructor (`super().__init__(app, "MyPlugin")`) and to use `layouts/module_admin.html` as admin template base.
> Also, `BasePlugin` provides both built-in routes: `/admin/<PluginName>` and `/page/<PluginName>`.

## The BasePlugin Class

`BasePlugin` provides all the core infrastructure. When `super().__init__(app, __name__)` is called, it:

- Registers a Flask Blueprint with the plugin's routes
- Loads configuration from the DB (`self.config`)
- Initialises the logger (`self.logger`)
- Sets up static files and templates

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `self.name` | `str` | Plugin name (from the folder name) |
| `self.title` | `str` | Display name |
| `self.description` | `str` | Plugin description |
| `self.category` | `str` | Category: `App`, `Devices`, `System` |
| `self.version` | `str` | Version |
| `self.system` | `bool` | System plugin (hidden from the general list) |
| `self.actions` | `list` | List of supported actions |
| `self.config` | `dict` | Configuration loaded from DB |
| `self.logger` | `Logger` | Plugin logger |

---

## Actions

Declare in `self.actions` the actions your plugin supports.

### `cycle` — background task

```python
self.actions = ['cycle']

def cyclic_task(self):
    """Called repeatedly in a loop in a background thread."""
    import time
    self.logger.debug("Cycle running")
    time.sleep(10)  # pause between iterations
```

> **Important:** `cyclic_task` runs in an infinite loop. Always add `time.sleep()` to avoid saturating the CPU.

### `proxy` — property change listener

```python
self.actions = ['proxy']

def changeProperty(self, obj, prop, value):
    """Called on every property change in the system."""
    if obj == "MotionSensor" and prop == "occupancy" and value:
        self.logger.info("Motion detected!")
        from app.core.lib.object import setProperty
        setProperty("HallLamp.state", True)
```

### `say` — speech / notification output

```python
self.actions = ['say']

def say(self, message: str, level: int = 0, args=None):
    """Called when the system wants to 'say' something."""
    self.logger.info(f"[TTS] {message}")
    self._synthesize_and_play(message)
```

### `playsound` — audio playback

```python
self.actions = ['playsound']

def playSound(self, file_name: str, level: int = 0):
    """Play an audio file."""
    import subprocess
    subprocess.Popen(["aplay", file_name])
```

### `widget` — Dashboard widget

```python
self.actions = ['widget']

def widget(self, name):
    """Return widget HTML for the Dashboard."""
    data = {"temperature": getProperty("HomeSensor.temperature")}
    return self.render("widget.html", data)
```

### `search` — global search

```python
self.actions = ['search']

def search(self, query: str) -> list:
    """Return search results for the given query."""
    results = []
    if query.lower() in "my device":
        results.append({
            "title": "My Device",
            "description": "Found in MyPlugin",
            "url": "/admin/MyPlugin"
        })
    return results
```

---

## Plugin Configuration

Plugin configuration is stored in the database as JSON. Use `self.config` to read and save settings.

```python
def initialization(self):
    host = self.config.get("host", "localhost")
    port = self.config.get("port", 1883)
    self.logger.info(f"Connecting to {host}:{port}")

def admin(self, request):
    if request.method == "POST":
        self.config["host"] = request.form.get("host", "localhost")
        self.config["port"] = int(request.form.get("port", 1883))
        self.saveConfig()
        return redirect(f"/admin/{self.name}")

    return self.render("my_plugin.html", {"config": self.config})
```

In the template:

```html
{% extends "base.html" %}
{% block content %}
<form method="POST">
    <label>Host:</label>
    <input type="text" name="host" value="{{ config.get('host', 'localhost') }}">

    <label>Port:</label>
    <input type="number" name="port" value="{{ config.get('port', 1883) }}">

    <button type="submit">Save</button>
</form>
{% endblock %}
```

---

## Working with Objects from a Plugin

```python
from app.core.lib.object import (
    addClass, addObject, addClassProperty,
    getProperty, setProperty, callMethod
)
from app.core.lib.constants import PropertyType

def initialization(self):
    # Create a class for the plugin's devices (if it doesn't exist)
    addClass("MyDevice", description="MyPlugin device", update=True)

    addClassProperty(
        name="state",
        class_name="MyDevice",
        description="Device state",
        type=PropertyType.Boolean,
        history=7  # keep 7 days of history
    )

def cyclic_task(self):
    import time
    state = self._poll_device()
    setProperty("MyDevice1.state", state)
    time.sleep(5)
```

---

## Registering Additional Routes

Besides `/admin/<Name>`, you can add extra routes by naming methods with the `route_` prefix:

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

## Sending Data to the Dashboard (WebSocket)

```python
from app.core.lib.common import sendDataToWebsocket

# Push an update to the browser
sendDataToWebsocket("update", {
    "object": "MyDevice1",
    "property": "state",
    "value": True
})

# Or via the BasePlugin method
self.sendDataToWebsocket("notification", {
    "message": "Device connected",
    "level": "info"
})
```

---

## Translations

Create translation files for internationalisation:

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

In templates use the `_()` function:

```html
<h2>{{ _('MyPlugin.title') }}</h2>
<label>{{ _('MyPlugin.host') }}:</label>
```

---

## Full Example: HTTP Monitor Plugin

A plugin that periodically checks URL availability and updates an object's state:

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
        self.description = "Monitor HTTP endpoint availability"
        self.category = "App"
        self.version = "0.1"
        self.actions = ["cycle"]

    def initialization(self):
        addClass("HttpEndpoint", description="HTTP endpoint", update=True)
        addClassProperty("online", "HttpEndpoint", type=PropertyType.Boolean)
        addClassProperty("response_time", "HttpEndpoint", type=PropertyType.Float, history=30)
        addClassProperty("url", "HttpEndpoint", type=PropertyType.String)

        for name, url in self.config.get("endpoints", {}).items():
            addObject(name, "HttpEndpoint", update=True)
            setProperty(f"{name}.url", url)

        self.logger.info("HttpMonitor initialized")

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

        time.sleep(60)  # check once per minute

    def admin(self, request):
        if request.method == "POST":
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

## Tips and Common Pitfalls

### Don't block `cyclic_task` with a long `time.sleep()`

If you need a long interval, use short sleeps with a stop-event check:

```python
def cyclic_task(self):
    import time
    self._do_work()
    # Wait 60 seconds but remain interruptible
    for _ in range(60):
        if self.event.is_set():
            break
        time.sleep(1)
```

### Don't do heavy work in `changeProperty`

`changeProperty` with `action="proxy"` is called on **every** property change in the system. Heavy code here will slow down the whole system. Filter early:

```python
def changeProperty(self, obj, prop, value):
    if obj != "MotionSensor":
        return
    if prop != "occupancy":
        return
    self._handle_motion(value)
```

### Logging

```python
self.logger.debug("Debug info")            # only shown when debug=True
self.logger.info("Normal event")
self.logger.warning("Warning")
self.logger.error("Error", exc_info=True)  # exc_info=True adds a stack trace
```

Logs are written to `logs/<PluginName>.log`.
