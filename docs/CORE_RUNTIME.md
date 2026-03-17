## Core runtime overview (EN)

This document describes several core subsystems that are frequently used by plugins and internal code:

- application configuration (`app/configuration.py`),
- scheduling and cron jobs (`app/core/lib/common.py`),
- notifications and WebSocket integration (`app/core/lib/common.py`, `app/api/utils/endpoints.py`),
- utility API (`app/api/utils/endpoints.py`).

It is a companion to `ARCHITECTURE.md`, which focuses on high‑level components.

---

### 1. Configuration (`Config`)

File: `app/configuration.py`

- `ConfigLoader`:
  - loads `config.yaml` and exposes values as attributes,
  - computes important paths:
    - `APP_DIR` — application package root (`app/`),
    - `PROJECT_ROOT` — repository root (one level above `app/`),
    - `PLUGINS_FOLDER` — directory with plugins (`<APP_DIR>/plugins`),
    - `FILES_DIR` — base directory for user files.
- Application section in `config.yaml` (`application:`):
  - `debug` — enables debug mode,
  - `app_port` — HTTP port,
  - `env` — environment name,
  - `pool_size`, `pool_max_size`, `pool_timeout_threshold` — thread pool settings,
  - `batch_writer_flush_interval` — flush interval for `BatchWriter`,
  - `session_lifetime_days` — session lifetime.
- Database section (`database:`):
  - `connection_string` (recommended) or SQLite fallback (`app.db` in `APP_DIR`),
  - `sqlalchemy_echo`, `pool_size`.
- Cache section (`cache:`):
  - `type` — cache backend (default: `simple`),
  - `file_path` — directory for file cache,
  - `timeout` — default TTL.
- Service section (`service:`):
  - `name` — systemd service name (optional),
  - `autorestart` — auto‑restart behaviour for service managers.

The global `Config` instance is created at import time and used by the rest of the app.

---

### 2. Scheduling and cron jobs

File: `app/core/lib/common.py`

Core concepts:

- Model `Task` (`app/core/models/Tasks.py`) stores scheduled jobs.
- All operations are wrapped in `session_scope()` (see `app/database.py`).
- Concurrency is protected by `get_task_lock(name)` which ensures only one thread modifies a job with the same name.

Key functions:

- `addScheduledJob(name, code, dt, expire=1800)`:
  - creates/updates a `Task` with:
    - `code` — Python code to execute,
    - `runtime` — UTC datetime when job should run,
    - `expire` — expiration time,
    - `active` flag.
- `addCronJob(name, code, crontab="* * * * *")`:
  - computes next run time using `nextStartCronJob`,
  - persists cron expression in the task,
  - marks it as active.
- `setTimeout(name, code, timeout=0)`:
  - helper that converts a timeout in seconds into `addScheduledJob` call.
- `clearScheduledJob(name)`, `clearTimeout(name)`:
  - delete tasks whose name matches pattern (via `LIKE`).
- `enableJob(name)`, `disableJob(name)`:
  - toggle `active` flag.
- `getJob(name)`, `getJobs(query)`:
  - read job metadata as plain dictionaries (`row2dict`).

Execution of the `code` field happens elsewhere in the scheduler loop (outside this module); the helpers here only manage persistence and locking.

---

### 3. Notifications and WebSocket integration

File: `app/core/lib/common.py`, model `app/core/models/Plugins.py` (`Notify`).

Notifications are stored in the database and mirrored in:

- system properties (`SystemVar.LastNotify`, `SystemVar.UnreadNotify`),
- WebSocket events (via `wsServer` plugin),
- REST API (`/api/utils/notifications*`).

Key helpers:

- `addNotify(name, description="", category=CategoryNotify.Info, source="")`:
  - finds or creates `Notify` record with the same `name`/`description` and `read == False`,
  - increments counter, updates timestamps,
  - updates object properties:
    - `SystemVar.LastNotify` — last notification payload,
    - `SystemVar.UnreadNotify` — boolean flag,
  - sends WebSocket event to plugin `wsServer` via `callPluginFunction("wsServer", "notify", {"data": ...})`.
- `readNotify(notify_id)`:
  - marks a single notification as read,
  - recalculates `SystemVar.UnreadNotify`,
  - emits `"read_notify"` WebSocket event.
- `readNotifyAll(source: Optional[str] = None)`:
  - marks all notifications as read, optionally filtered by `source`,
  - updates `SystemVar.UnreadNotify`,
  - emits `"read_notify_all"` WebSocket event.

WebSocket helpers:

- `sendWebsocket(command, data, client_id=None)`:
  - delegates to `wsServer.sendCommand(...)` if the plugin is loaded.
- `sendDataToWebsocket(typeData, data)`:
  - delegates to `wsServer.sendData(...)`.

These functions are generic and can be reused by plugins to push custom events to connected clients.

---

### 4. Utility API (`/api/utils`)

File: `app/api/utils/endpoints.py`

Namespace: `utils_ns = Namespace(name="utils", ...)`.

Main resources:

- `GET /api/utils/search`:
  - global search across plugins that declare `"search"` in their `actions`,
  - for each plugin, calls `plugin.search(query)` and accumulates results (up to `limit`),
  - results are rendered via `search_result.html` and cached using `cache` extension.
- `GET /api/utils/readnotify/<id>`:
  - marks single notification as read using `readNotify`.
- `GET /api/utils/readnotify/all`:
  - marks notifications as read using `readNotifyAll(source)`.
- `POST /api/utils/validate-python`:
  - validates Python code using `ast.parse`,
  - returns a list of errors compatible with the Ace editor (0‑based indexes).
- `GET /api/utils/intelli-python`:
  - returns cached symbols from `current_app.extensions['intelli_cache']`.
- `POST /api/utils/lsp/python`:
  - thin bridge to `run_lsp_action` (`completion`, `hover`, `diagnostics`, `signature`),
  - requires `action`, `code`, optional position and binding information.
- `POST /api/utils/run`:
  - executes arbitrary Python code via `runCode` from `app.core.lib.common`,
  - returns captured output and success flag.
- `POST /api/utils/crontask`:
  - creates/updates a cron task for an object method:
    - `method` — `"ObjectName.method_name"`,
    - `crontab` — schedule expression,
  - internally uses `addCronJob` / `clearScheduledJob`.
- `GET /api/utils/notifications`:
  - returns list of notifications with optional filters:
    - `source`,
    - `unread_only` (default: `true`).
- `GET /api/utils/notifications/stats`:
  - returns aggregated statistics:
    - total notifications,
    - unread count,
    - counts per `source`.

All utility endpoints are protected by API key and admin/user decorators (`api_key_required`, `handle_admin_required`, `handle_user_required`) depending on sensitivity.

---

### 5. Other helpers in `common.py`

- `getModule(name)` / `getModulesByAction(action)`:
  - read from plugin registry (`PluginsHelper.plugins`) and return plugin instances.
- `say(message, level=0, args=None)`:
  - updates `SystemVar.LastSay`,
  - dispatches `say(...)` calls to plugins that declare `"say"` in `actions` using `MonitoredThreadPool`.
- `playSound(file_name, level=0, args=None)`:
  - dispatches `playSound(...)` calls to `"playsound"` plugins.
- `requestUrl(url, method=...)`, `getUrl(url, ...)`, `postUrl(url, ...)` и др.:
  - simple `requests.get` wrapper with logging.
- `xml_to_dict(xml_data)`:
  - converts XML string into nested dictionary.
- `runCode(code, args=None)`:
  - executes dynamic Python code with a small predefined environment (`params`, `logger`),
  - returns captured output and success flag.
- `is_datetime_in_range(check_dt, start_dt, end_dt, inclusive=True)`:
  - normalises datetimes to naive UTC and checks whether `check_dt` is inside the range with flexible boundary inclusion.

These utilities are shared between core code and plugins, and form the “glue” for timers, notifications and integrations.

---

## Обзор ядра и рантайма (RU)

Ниже — краткий обзор основных подсистем ядра. Подробные диаграммы смотрите в `ARCHITECTURE.md`.

### 1. Конфигурация (`Config`)

- Файл `app/configuration.py` загружает `config.yaml` и создаёт глобальный объект `Config`.
- Важные группы настроек:
  - `application` — порт, режим `debug`, таймауты сессий, параметры потокового пула и `BatchWriter`.
  - `database` — строка подключения или SQLite‑файл по умолчанию.
  - `cache` — тип кеша и каталог для файлового кеша.
  - `service` — имя systemd‑сервиса и поведение авто‑рестарта.
- Пути `APP_DIR`, `PROJECT_ROOT`, `PLUGINS_FOLDER`, `FILES_DIR` используются всем приложением и плагинами для поиска модулей и файлов.

### 2. Планировщик задач и cron

- `addScheduledJob`, `addCronJob`, `setTimeout`, `clearScheduledJob` управляют задачами в таблице `Task`.
- `get_task_lock` гарантирует, что для каждого имени задачи изменения происходят последовательно.
- Крон‑задачи используют функцию `nextStartCronJob` и позволяют вызывать методы объектов по расписанию (см. `/api/utils/crontask`).

### 3. Уведомления и WebSocket

- `addNotify`, `readNotify`, `readNotifyAll` работают с моделью `Notify` и системными переменными `SystemVar.LastNotify` и `SystemVar.UnreadNotify`.
- Для фронтенда события дублируются в WebSocket через плагин `wsServer` (`sendWebsocket`, `sendDataToWebsocket` и `callPluginFunction`).
- REST‑эндпоинты `/api/utils/notifications*` позволяют читать список уведомлений и статистику по ним.

### 4. Вспомогательные API (`/api/utils`)

- Глобальный поиск (`/search`) агрегирует результаты от плагинов с действием `"search"`.
- Проверка Python‑кода (`/validate-python`) и запуск кода (`/run`) используются в редакторе сценариев.
- LSP‑мост (`/lsp/python`) обеспечивает автодополнение, подсказки и диагностику прямо в браузере.
- Настройка cron‑задач (`/crontask`) упрощает запуск методов объектов по расписанию без прямой работы с таблицей `Task`.

### 5. Утилиты общего назначения

- `say` и `playSound` рассылают сообщения/звуки во все плагины, поддерживающие соответствующие действия.
- `xml_to_dict`, `requestUrl`/`getUrl`, `runCode`, `is_datetime_in_range` и другие функции упрощают написание плагинов и внутренних сервисов.

Для более глубокого понимания объекта‑ориентированного ядра смотрите также `ARCHITECTURE.md`, `PARAMS_DOCUMENTATION.md` и примеры в `tests/test_object_manager.py`.

