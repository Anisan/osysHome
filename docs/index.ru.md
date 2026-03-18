# osysHome — Документация

**osysHome** (Object System smartHome) — это открытая платформа для автоматизации умного дома на Python. Система построена вокруг объектно-ориентированной модели устройств и расширяется через плагины.

---

## С чего начать

Если вы только знакомитесь с системой, читайте документы в этом порядке:

| Шаг | Документ | Что узнаете |
|-----|----------|-------------|
| 1 | [Установка и первый запуск](getting-started.ru.md) | Как развернуть систему с нуля |
| 2 | [Конфигурация](configuration.ru.md) | Как настроить `config.yaml` |
| 3 | [Основные концепции](core-concepts.ru.md) | Что такое классы, объекты, свойства и методы |
| 4 | [Связывание свойств с плагинами](binding.ru.md) | Как виртуальные объекты связываются с реальными устройствами |
| 5 | [Веб-интерфейс](web-interface.ru.md) | Как работать с системой через браузер |
| 6 | [Автоматизации](automation.ru.md) | Как создавать сценарии и расписания |
| 7 | [Плагины](plugins.ru.md) | Как подключать и настраивать плагины |
| 8 | [Разработка плагинов](plugin-development.ru.md) | Как написать собственный плагин |

---

## Архитектура системы

```
osysHome
├── app/                  — ядро системы (Flask, БД, ObjectManager)
│   ├── core/
│   │   ├── main/         — BasePlugin, PluginsHelper, ObjectManager
│   │   ├── lib/          — публичное API: object.py, common.py
│   │   └── models/       — модели БД: Class, Object, Property, Value, Method
│   ├── api/              — REST API
│   └── admin/            — административные маршруты
├── plugins/              — плагины (каждый — отдельная папка)
├── docs/                 — документация (эта папка)
├── config.yaml           — основной файл конфигурации
└── main.py               — точка входа
```

### Ключевые компоненты

- **ObjectManager** — движок, хранящий состояние всех устройств в БД и оперативной памяти  
- **BasePlugin** — базовый класс, от которого наследуют все плагины  
- **PluginsHelper** — обнаружение, загрузка и запуск плагинов при старте  
- **Scheduler** — системный плагин для выполнения задач по расписанию  
- **Dashboard** — веб-интерфейс и виджеты на главной странице  

---

## Поддерживаемые протоколы и интеграции

| Категория | Плагины |
|-----------|---------|
| Устройства | MQTT, Zigbee2MQTT (z2m), Tuya, ESPHome, Bluetooth, Modbus, OpenHASP |
| Умные дома | Xiaomi Home, Yandex Devices, ThinQ (LG), Hisense TV, Keenetic |
| Речь / TTS | Google TTS, Yandex TTS, Yandex SpeechKit |
| Уведомления | Telegram Bot |
| Расположение | GPS Tracker, Google Location, Friends2GIS |
| Система | Backup, Scheduler, Modules, Objects, Users, ConsoleMonitor |

---

## Системные требования

- Python 3.10+
- SQLite (по умолчанию) или PostgreSQL / MySQL
- Linux / Windows / macOS
- Браузер для веб-интерфейса
