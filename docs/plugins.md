# Plugins

Plugins are the extension mechanism in osysHome.  
This document describes the core lifecycle and management flow without plugin-specific instructions.

---

## How Plugin Loading Works

On startup, osysHome:
1. Scans the `plugins/` directory
2. Treats each subdirectory as a plugin candidate
3. Checks activation state in the database
4. Imports and initializes active plugins

Inactive plugins are skipped.

---

## Plugin Management in UI

Use **Admin → Modules** to:
- View installed plugins
- Enable or disable plugins
- Open plugin settings pages

> A restart may be required for lifecycle changes to be applied.

---

## Installing a Plugin (Generic)

1. Put the plugin folder inside `plugins/`
2. Ensure `__init__.py` exists and exposes the plugin class
3. Install dependencies (if `requirements.txt` is present)
4. Restart osysHome
5. Enable/configure the plugin in **Admin → Modules**

---

## Where Plugin Documentation Lives

Documentation for concrete plugins is maintained with each plugin:
- `plugins/<PluginName>/README.md`
- `plugins/<PluginName>/README.ru.md`
- optional `docs/` inside the plugin directory
