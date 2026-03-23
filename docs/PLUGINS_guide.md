## Plugins guide (EN)

This document explains how plugins work in osysHome, how to structure them, and how they interact with objects, the database and the UI.

---

### 1. What is a plugin?

A **plugin** is a Python package under the `plugins/` directory that:

- Extends the system with new logic (integrations, schedulers, hardware, etc.).
- Can expose:
  - admin pages (under `/admin/<PluginName>`),
  - public pages (under `/page/<PluginName>`),
  - dashboard widgets,
  - background tasks (cycle),
  - search providers,
  - property change observers (`proxy`),
  - sound/notification output.

Technically, every plugin:

- Has a directory: `plugins/<PluginName>/`.
- Contains an `__init__.py` that defines a class inheriting from `BasePlugin`.
- May contain `templates/` and `static/` for UI.
- May store configuration in the DB (`Plugin` model) and translations in `translations/*.json`.

---

### 2. Lifecycle overview

1. Flask app is created in `app/__init__.py` (`createApp`).
2. `registerPlugins(app)` from `app/core/main/PluginsHelper.py` scans the `plugins/` directory.
3. For each plugin:
   - Its module is imported.
   - Plugin class (subclass of `BasePlugin`) is instantiated: `MyPlugin(app)`.
   - `BasePlugin.__init__`:
     - loads config from DB (table `Plugins`),
     - creates and registers a Flask `Blueprint`,
     - auto‑registers routes from any `route_*` methods,
     - sets up logging.
   - Plugin is stored in an internal registry.
4. When the system starts (see `main.py` and `start_plugins()`):
   - Each plugin’s `initialization()` method is called.
   - If plugin declares `actions` that include `"cycle"`, its `start_cycle()` is called which spawns a background thread and repeatedly calls `cyclic_task()`.
5. On shutdown (`stop_plugins()`):
   - Plugins can stop background tasks (`stop_cycle()`), flush state, etc.

---

### 3. BasePlugin essentials

File: `app/core/main/BasePlugin.py`

Key fields and behaviours:

- `name` — plugin identifier, equals directory name under `plugins/`.
- `title`, `description`, `category`, `author`, `version` — metadata for UI.
- `actions: list[str]` — supported actions; conventions:
  - `"cycle"` — plugin has a background loop (`cyclic_task()`).
  - `"search"` — plugin provides search results (implements `search()`).
  - `"widget"` — plugin renders widgets for the dashboard (implements `widgets()` / `widget()`).
  - `"say"` — plugin can output messages/notifications (implements `say()`).
  - `"proxy"` — plugin observes all property changes (implements `changeProperty()`).
  - `"playsound"` — plugin can play sounds (implements `playSound()`).
- `config: dict` — plugin configuration stored in the DB (`Plugin` table, JSON).
- `logger` — plugin‑specific logger configured via `level_logging` in `config`.
- `blueprint` — Flask `Blueprint` auto‑registered with:
  - `template_folder = plugins/<name>/templates`
  - `static_folder = plugins/<name>/static`
  - `static_url_path = /<name>/static`

Important methods to override:

- `initialization(self)` — called once at plugin startup.
- `admin(self, request)` — returns admin page content for `/admin/<name>` (provided by `route_admin`).
- `page(self, request)` — optional page for `/page/<name>` (provided by `route_page`).
- `cyclic_task(self)` — if `"cycle"` in `actions`.
- `search(self, query: str)` — if `"search"` in `actions`.
- `changeProperty(...)`, `changeObject(...)`, `say(...)`, `playSound(...)` — for corresponding actions.
- `widgets(self)` and `widget(self, name: str)` — for `"widget"` actions.

Helper methods:

- `render(template: str, content: dict)` — render Jinja template inside plugin context.
- `loadConfig()`, `saveConfig()` — loading/saving plugin configuration from/to DB.
- `sendDataToWebsocket(operation: str, data: dict)` — push data to WebSocket subscribers.

---

### 4. Directory structure of a plugin

Minimal plugin:

```text
plugins/
  MyFirstPlugin/
    __init__.py
    templates/
      admin.html
    static/
      my_plugin.css
      my_plugin.js
    translations/
      en.json
      ru.json
```

Notes:

- `templates/` and `static/` are optional; if not needed, you can skip them.
- `translations/*.json` follow the same structure as main app translation files.
- Plugin name (`MyFirstPlugin`) must match the class name argument passed to `BasePlugin` and directory name.

---

### 5. Example: simple admin plugin

`plugins/MyFirstPlugin/__init__.py`:

```python
from app.core.main.BasePlugin import BasePlugin


class MyFirstPlugin(BasePlugin):
    def __init__(self, app):
        super().__init__(app, "MyFirstPlugin")
        self.title = "My First Plugin"
        self.description = "Simple example plugin"
        self.category = "Examples"
        self.author = "Your Name"
        self.version = 1
        self.actions = []  # later you can add: ["widget", "search", "cycle", "proxy"]

    def initialization(self):
        # Called at system startup
        self.logger.info("MyFirstPlugin initialized")

    def admin(self, request):
        # Admin page is available at /admin/MyFirstPlugin
        context = {
            "title": self.title,
            "description": self.description,
        }
        return self.render("admin.html", context)
```

`plugins/MyFirstPlugin/templates/admin.html`:

```html
{% extends "layouts/module_admin.html" %}
{% block title %} {{ _('My First Plugin') }} {% endblock %}

{% block module %}
<div class="row">
  <div class="col-12">
    <div class="card">
      <div class="card-body">
        <h3 class="card-title">{{ _('My First Plugin') }}</h3>
        <p class="card-text">
          {{ _('This is a simple example of a plugin admin page.') }}
        </p>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

Steps to enable:

1. Create the directory `plugins/MyFirstPlugin/` and files as above.
2. Restart osysHome (`python main.py`).
3. Open `/admin/MyFirstPlugin` in the browser (via Control panel → Modules/Plugins list or direct URL).

---

### 6. Example: widget‑enabled plugin

To show widgets on the main dashboard (`/admin` → control panel), use:

- `actions` contains `"widget"`,
- implement `widgets()` and `widget(name)`.

Sketch:

```python
class MyFirstPlugin(BasePlugin):
    def __init__(self, app):
        super().__init__(app, "MyFirstPlugin")
        self.title = "My First Plugin"
        self.description = "Demo with a widget"
        self.category = "Examples"
        self.actions = ["widget"]

    def widgets(self):
        # Returned structures may be used by dashboard plugins
        return [
            {"name": "info", "description": "MyFirstPlugin info widget"}
        ]

    def widget(self, name: str = None) -> str:
        # Called when dashboard needs HTML for the widget
        # You can switch by name if you have several widgets
        return self.render("widget_info.html", {"title": self.title})
```

In `templates/widget_info.html` you can create a small card compatible with dashboard layout.

Actual rendering and placement of widgets on the control panel is done by dashboard‑type plugins (e.g. `osysHome-Dashboard`), which call `widgets()`/`widget()` on registered plugins.

---

### 7. Interacting with objects and the DB

Inside a plugin you can use the same helpers as the rest of the app:

```python
from app.core.lib.object import getObject, getObjectsByClass, setProperty

class MyFirstPlugin(BasePlugin):
    ...

    def initialization(self):
        # Example: ensure some system object exists
        obj = getObject("DemoObject")
        if not obj:
            # you can add classes/objects via app.core.lib.object helpers
            self.logger.info("DemoObject is not created yet")

    def cyclic_task(self):
        # Example: periodic check
        objs = getObjectsByClass("SomeClass")
        for obj in objs:
            value = obj.getProperty("temperature")
            if value and value > 30:
                self.logger.warning("High temperature on %s: %s", obj.name, value)
```

For low‑level DB access you can use `session_scope` from `app.database`, but in most cases object helpers are preferred.

---

### 8. Recommended structure & best practices

- Keep plugin responsibilities focused (one main integration or feature per plugin).
- Use `actions` only when really needed (avoid unnecessary background threads).
- Store configuration in plugin `config` and expose a simple admin UI to edit it.
- Use translations (`translations/en.json`, `translations/ru.json`) for user‑visible text.
- Reuse existing CSS/JS from the main app when possible to keep UI consistent.

---

## Гайд по плагинам (RU)

Краткое резюме на русском:

- Плагин — это каталог `plugins/<ИмяПлагина>/` с `__init__.py`, опциональными `templates/`, `static/`, `translations/`.
- Класс плагина наследуется от `BasePlugin` и создаётся в момент запуска приложения (`registerPlugins`).
- Основные точки расширения:
  - `initialization()` — инициализация при старте.
  - `admin(request)` — страница админки `/admin/<ИмяПлагина>`.
  - `page(request)` — публичная страница `/page/<ИмяПлагина>`.
  - `cyclic_task()` — фоновый цикл при наличии `"cycle"` в `actions`.
  - `search(query)` — поиск по объектам/данным плагина.
  - `changeProperty(...)`, `changeObject(...)` — реакция на изменения свойств/структуры объектов.
  - `widgets()` / `widget(name)` — виджеты для панели управления.
- Подробный, актуальный и полнокодовый пример смотрите в английской части этого файла и исходнике `BasePlugin` (`app/core/main/BasePlugin.py`).

Рекомендуется:

- Начать с простого плагина с одной страницей админки.
- Затем добавить виджет и/или фоновую задачу по мере необходимости.
- Использовать `docs/QUICKSTART_dev.md` как стартовую точку и смотреть примеры из внешних репозиториев (`osysHome-Dashboard`, `osysHome-Scheduler` и т.п.) для реальных кейсов.

