# osysHome — Documentation

**osysHome** (Object System smartHome) is an open-source Python smart home automation platform. The system is built around an object-oriented device model and extended through plugins.

---

## Getting Started

If you are new to the system, read the documents in this order:

| Step | Document | What you'll learn |
|------|----------|-------------------|
| 1 | [Installation & First Run](getting-started.md) | How to deploy the system from scratch |
| 2 | [Configuration](configuration.md) | How to configure `config.yaml` |
| 3 | [Core Concepts](core-concepts.md) | What classes, objects, properties, and methods are |
| 4 | [Property–Plugin Binding](binding.md) | How virtual objects are linked to real physical devices |
| 5 | [Web Interface](web-interface.md) | How to use the system through a browser |
| 6 | [Automations](automation.md) | How to create scenarios and schedules |
| 7 | [Plugins](plugins.md) | How to connect and configure plugins |
| 8 | [Plugin Development](plugin-development.md) | How to write your own plugin |

---

## System Architecture

```
osysHome
├── app/                  — core system (Flask, DB, ObjectManager)
│   ├── core/
│   │   ├── main/         — BasePlugin, PluginsHelper, ObjectManager
│   │   ├── lib/          — public API: object.py, common.py
│   │   └── models/       — DB models: Class, Object, Property, Value, Method
│   ├── api/              — REST API
│   └── admin/            — admin routes
├── plugins/              — plugins (each is a separate folder)
├── docs/                 — documentation (this folder)
├── config.yaml           — main configuration file
└── main.py               — entry point
```

### Key Components

- **ObjectManager** — engine that stores all device state in the DB and in-memory cache
- **BasePlugin** — base class inherited by all plugins
- **PluginsHelper** — plugin discovery, loading, and startup
- **Scheduler** — system plugin for executing scheduled tasks
- **Dashboard** — web interface and widgets on the main page

---

## Supported Protocols & Integrations

| Category | Plugins |
|----------|---------|
| Devices | MQTT, Zigbee2MQTT (z2m), Tuya, ESPHome, Bluetooth, Modbus, OpenHASP |
| Smart Home | Xiaomi Home, Yandex Devices, ThinQ (LG), Hisense TV, Keenetic |
| Speech / TTS | Google TTS, Yandex TTS, Yandex SpeechKit |
| Notifications | Telegram Bot |
| Location | GPS Tracker, Google Location, Friends2GIS |
| AI | AIAutomation, AIRecommender |
| System | Backup, Scheduler, Modules, Objects, Users, ConsoleMonitor |

---

## System Requirements

- Python 3.10+
- SQLite (default) or PostgreSQL / MySQL
- Linux / Windows / macOS
- A browser for the web interface
