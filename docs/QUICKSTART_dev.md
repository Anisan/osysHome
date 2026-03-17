## Developer quickstart (EN)

This guide is for Python developers who want to extend osysHome, write plugins, or integrate it into their own automation.

---

### 1. Repo, environment, dependencies

```bash
git clone https://github.com/Anisan/osysHome.git
cd osysHome

python3 -m venv venv    # or python on Windows
source venv/bin/activate

pip install -r requirements.txt
```

Install recommended plugins (objects, users, scheduler, dashboard, wsServer) to get a realistic environment:

```bash
mkdir -p plugins
./scripts/install_recommended_plugins.sh          # Linux/macOS
.\scripts\install_recommended_plugins.ps1         # Windows PowerShell
```

Create `config.yaml` from the sample and enable `debug`:

```bash
cp sample_config.yaml config.yaml      # Linux
Copy-Item sample_config.yaml config.yaml   # Windows
```

In `config.yaml`:

```yaml
application:
  debug: true
```

Run the app:

```bash
python main.py
```

---

### 2. High‑level architecture

- **Entry point**
  - `main.py` — creates Flask app via `createApp(Config)` and runs the server.
- **Flask app factory**
  - `app/__init__.py` — `createApp`:
    - config & DB setup
    - register blueprints: `api`, `authentication`, `admin`, `files`
    - sync DB schema
    - load plugins via `registerPlugins`
    - install translations and Jinja context helpers.
- **Core object system**
  - `app/core/main/ObjectManager.py`
    - `ObjectManager` — wrapper around DB model `Object` with `properties` and `methods`.
    - `PropertyManager` — validation, history, type conversion, `params` (see `PARAMS_DOCUMENTATION.md`).
  - `app/core/lib/object.py` (not detailed here, used via helpers like `getObject`, `setProperty`).
- **Plugins**
  - `plugins/` — each plugin is a directory with its own Flask blueprint, templates, static, etc.
  - `app/core/main/BasePlugin.py` — base class for plugins (see below).
- **API**
  - `app/api/*` — REST routes for objects, properties, methods, import/export.

See `ARCHITECTURE.md` for diagrams and more details.

---

### 3. Running in dev mode

Key config switches in `config.yaml`:

- `application.debug: true` — enables Flask/SQLAlchemy debug options (see `app/__init__.py`).
- `database.sqlalchemy_echo: true` (optional) — log SQL queries.

You can run tests to verify the core behaves as expected:

```bash
python -m unittest discover tests -v
```

See `tests/README.md` for more details and targeted test runs.

---

### 4. Working with objects from Python

The object system is accessible via helper functions from `app.core.lib.object`.

Example (pseudo‑usage, adjust imports to your style):

```python
from app.core.lib.object import getObject, addObject, addObjectProperty
from app.core.lib.constants import PropertyType

# Create an object class and an instance (if not yet created)
addObject("DemoObject", None, "Demo object")
obj = getObject("DemoObject")

# Ensure we have a property
addObjectProperty("temperature", "DemoObject", "Temperature", 7, PropertyType.Float)

# Set and get property value
obj.setProperty("temperature", 23.5, source="script")
current = obj.getProperty("temperature")
print(current)
```

For property parameters (`min`, `max`, `step`, `allowed_values`, `enum_values`, etc.) and validation, see:

- `PARAMS_DOCUMENTATION.md`
- `ENUM_TYPE_USAGE.md`

---

### 5. Creating your first plugin

Plugins live under `plugins/<PluginName>/` and must inherit from `BasePlugin`.

Directory structure:

```text
plugins/
  MyFirstPlugin/
    __init__.py
    templates/
      admin.html
    static/
      ...
```

`plugins/MyFirstPlugin/__init__.py`:

```python
from app.core.main.BasePlugin import BasePlugin


class MyFirstPlugin(BasePlugin):
    def __init__(self, app):
        super().__init__(app, "MyFirstPlugin")
        self.title = "My First Plugin"
        self.description = "Simple example plugin"
        self.category = "Examples"
        self.actions = []  # e.g. ["widget", "cycle", "search", "proxy"]

    def initialization(self):
        # Called when plugin starts
        self.logger.info("MyFirstPlugin initialized")

    def admin(self, request):
        # Admin page under /admin/MyFirstPlugin
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
<div class="card">
  <div class="card-body">
    <h3 class="card-title">{{ _('My First Plugin') }}</h3>
    <p class="card-text">{{ _('This is a simple plugin admin page.') }}</p>
  </div>
</div>
{% endblock %}
```

How it works:

- `BasePlugin.__init__` creates a Flask `Blueprint` with:
  - `template_folder` = `<PluginName>/templates`
  - `static_folder`   = `<PluginName>/static`
  - routes `route_*` methods auto‑registered.
- `route_admin` registers `/admin/<PluginName>` and calls `self.admin(request)` (decorated by `handle_admin_required`).

For a deeper explanation of plugin lifecycle and supported `actions` see `docs/PLUGINS_guide.md`.

---

### 6. Adding widgets to the control panel

Plugins can expose widgets for the main dashboard by implementing:

- `actions` contains `"widget"`.
- `widgets()` returns a list of widget descriptors.
- `widget(name: str)` returns rendered HTML.

See existing dashboard‑related plugins in external repos (e.g. `osysHome-Dashboard`) for real examples, and `BasePlugin.widgets`/`BasePlugin.widget` docstrings for the contract.

The dashboard view template is `app/templates/control_panel.html`.

---

### 7. API usage

The REST API blueprint lives in `app/api`. Key groups:

- `app/api/objects/endpoints.py` — operations on objects.
- `app/api/properties/endpoints.py` — operations on properties and values.
- `app/api/methods/endpoints.py` — calling methods.

Typical pattern from an external client:

```python
import requests

BASE_URL = "http://localhost:5000/api"

resp = requests.get(f"{BASE_URL}/objects")
resp.raise_for_status()
objects = resp.json()
print(objects)
```

Look into `app/api/*/endpoints.py` for path details and request/response formats.

---

### 8. Tests and development workflow

- Run all tests:

```bash
python -m unittest discover tests -v
```

- Focus on object system:
  - `tests/test_object_manager.py`
  - `tests/test_property_validation.py`
  - `tests/test_advanced_validation.py`

Typical dev loop:

1. Edit code or plugin.
2. Run relevant tests (or full suite).
3. Start `python main.py` and check via web UI.
4. Use logs (see `app/logging_config.py`) for debugging.

---

### 9. Next steps

- `docs/ARCHITECTURE.md` — architecture diagrams and glossary.
- `docs/PLUGINS_guide.md` — deep dive into plugin structure and actions.
- `PARAMS_DOCUMENTATION.md` — advanced property validation.
- `MIGRATION_ENUM_VALUES.md` — enum format migration and reasons.

---

## Быстрый старт для разработчиков (RU)

Это руководство для Python‑разработчиков, которые хотят расширять osysHome, писать плагины или встраивать систему в свои сценарии автоматизации.

Структура полностью аналогична английской части:

1. Клонирование репозитория, venv, `pip install -r requirements.txt`
2. Установка рекомендованных плагинов (`scripts/install_recommended_plugins.*`)
3. Включение `debug` в `config.yaml`
4. Обзор архитектуры (см. `docs/ARCHITECTURE.md`)
5. Примеры работы с объектами через `ObjectManager` и функции из `app.core.lib.object`
6. Пример первого плагина в `plugins/MyFirstPlugin/`
7. Виджеты на панели (`actions=["widget"]`, см. `control_panel.html`)
8. Запуск и использование API (`app/api/*`)
9. Тесты и рабочий цикл разработки (`tests/*`)

Подробные примеры кода и объяснения смотрите в английской части файла выше — она является основной, чтобы избежать дублирования логики. Для интерфейса и сообщений в самом приложении предусмотрены переводы (EN/RU/DE), а при необходимости вы можете сгенерировать/обновить JSON‑файлы переводов с помощью `scripts/create_translations.py`.

