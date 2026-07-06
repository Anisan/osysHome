## Core runtime overview (EN)

This document describes several core subsystems that are frequently used by plugins and internal code:

- application configuration (`app/configuration.py`),
- scheduling and cron jobs (`app/core/lib/common.py`),
- notifications and WebSocket integration (`app/core/lib/common.py`, `app/api/utils/endpoints.py`),
- utility API (`app/api/utils/endpoints.py`).

It is a companion to `ARCHITECTURE.md`, which focuses on high‑level components.

Related docs:
- [Architecture](ARCHITECTURE.md)
- [Boot Sequence](BOOT_SEQUENCE.md)
- [Security & Access](SECURITY_ACCESS.md)
- [Consistency & Timezones](CONSISTENCY_TIMEZONES.md)

---

### 1. Configuration (`Config`)

File: `app/configuration.py`

- `ConfigLoader`:
  - loads `config.yaml` and exposes values as attributes,
  - computes important paths:
    - `APP_DIR` — repository root (project root),
    - `PLUGINS_FOLDER` — directory with plugins (`<APP_DIR>/plugins`),
    - `FILES_DIR` — base directory for user files.
- Application section in `config.yaml` (`application:`):
  - `debug` — enables debug mode,
  - `app_port` — HTTP port,
  - `env` — environment name,
  - `pool_size`, `pool_max_size`, `pool_timeout_threshold` — thread pool settings,
  - `batch_writer_flush_interval` — flush interval for `BatchWriter`,
  - `reactive_max_depth` — max depth of synchronous property→method chains (default `20`),
  - `reactive_loop_notify` — send admin notification when a reactive loop is blocked,
  - `object_preload_enabled` — background preload of all objects after `start_plugins()`,
  - `object_preload_batch_size`, `object_preload_interval_sec` — batch size and pause between batches,
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

### 6. ReactiveChain (property→method loop guard)

File: `app/core/main/reactive_chain.py`

During synchronous `ObjectManager.setProperty`, the core tracks `(object_name, property_name)` on a per-thread stack. Revisiting the same pair or exceeding `reactive_max_depth` **aborts** the update: no value change, no bound method call, error log, optional `addNotify`, and trace in `self.runtime["last_reactive_loop"]`.

Async paths (`setPropertyThread`, linked plugins, proxy) are not wrapped.

### 7. Object runtime and lifecycle hooks

- `ObjectManager.runtime` — in-memory dict, cleared on reload.
- Reserved methods `onInit` / `onStop` — invoked on lazy load, reload, and shutdown (`system:onInit` / `system:onStop`).
- `ObjectsStorage.start_background_preload()` — daemon thread after `start_plugins()`; logs `Preloaded N/M objects`.

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
- Пути `APP_DIR`, `PLUGINS_FOLDER`, `FILES_DIR` используются всем приложением и плагинами для поиска модулей и файлов.

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

### 6. ReactiveChain (защита от петель property→method)

Файл: `app/core/main/reactive_chain.py`

При синхронном `setProperty` ядро ведёт цепочку `(object, property)` в `threading.local()`. Повтор той же пары или превышение `reactive_max_depth` **обрывает** цепочку: значение не меняется, метод не вызывается, пишется лог и (опционально) notify. Trace сохраняется в `self.runtime["last_reactive_loop"]` объекта-инициатора.

Асинхронные пути (`setPropertyThread`, linked, proxy) не оборачиваются — у них отдельный root chain в своём потоке.

### 7. Object runtime и lifecycle

- `ObjectManager.runtime` — in-memory dict, очищается при reload.
- `onInit` / `onStop` — зарезервированные методы; вызываются из `ObjectsStorage` при lazy load, reload и shutdown.
- `ObjectsStorage.start_background_preload()` — daemon-поток после `start_plugins()`; лог `Preloaded N/M objects`.

Для более глубокого понимания объекта‑ориентированного ядра смотрите также `ARCHITECTURE.md`, `PARAMS_DOCUMENTATION.md` и примеры в `tests/test_object_manager.py`.

### 8. SystemStats (локальная аналитика)

Включение: `SystemVar.system_stats` = `true` (по умолчанию `false`). Отдельно от `SystemVar.analytics_enabled` (отправка на osysHome.ru).

Объект **`SystemStats`** — внутренний singleton (`initSystemStats()` в `app/utils.py`). Свойства с `params.internal=true` и `history=30` (дни хранения history).

**Режим:** только **event-driven** (без cron/collector). Метрики пишутся в точке события в ядре или в плагинах.

#### Защита от искажения аналитики (anti-loop)

Записи в `SystemStats` не раздувают сами счётчики активности:

- `track_stats=False` при записи метрик;
- `source=osysHome:system_stats` (или `osysHome:system_stats:<plugin>`);
- `ValueUpdate.internal` в BatchWriter;
- объект `SystemStats` в `SYSTEM_STATS_EXCLUDED_OBJECTS` — не участвует в агрегатах `ObjectsStorage.getStats()`.

Proxy/linked fan-out для записей `SystemStats` отключён; WebSocket — через debounce (`scheduleSystemStatsWsNotify`, 0.5 с).

#### Метрики ядра (`SystemStats.<name>`)

Регистрируются при старте в `initSystemStats()`. Пишутся через `writeCoreSystemStatsMetric` / `incrementCoreSystemStatsMetric` (`app/core/lib/common.py`).

| Свойство | Тип | Когда обновляется |
|----------|-----|-------------------|
| `property_reads` | int | каждое `getValue(track_stats=True)` вне internal-свойств |
| `property_writes` | int | каждое `setValue` вне internal-свойств |
| `methods_executed` | int | каждый `callMethod` (кроме объекта `SystemStats`) |
| `reactive_loops` | int | срабатывание reactive loop (`_record_reactive_loop`) |
| `batch_queue_size` | int | после flush BatchWriter (текущая очередь, обычно 0) |
| `batch_avg_flush_ms` | float | длительность последнего flush BatchWriter, мс |
| `batch_values_updated` | int | +N внешних обновлений Value за flush |
| `batch_history_inserted` | int | +N внешних вставок History за flush |
| `batch_total_errors` | int | +1 при ошибке внешнего batch flush |

**Буферизация горячих счётчиков:** `property_reads`, `property_writes`, `methods_executed`, `reactive_loops` накапливают дельты в памяти и сбрасываются на каждом тике BatchWriter (~0.5 с). Flush делает **атомарный инкремент в БД** (`SELECT … FOR UPDATE` + `+delta`), затем синхронизирует runtime-кэш — счётчики монотонно растут даже при нескольких worker-процессах.

Остальные core-метрики (`batch_*`) пишутся сразу при событии flush.

**Производительность:** флаг `SystemVar.system_stats` кэшируется на 2 с (`_is_system_stats_enabled`). При `false` инкременты не выполняются.

#### Метрики плагинов (`SystemStats.plugin_<Plugin>_<metric>`)

API в `app/core/lib/common.py`. Имена свойств: префикс `plugin_` + имя плагина + `_` + имя метрики (небезопасные символы → `_`).

```python
from app.core.lib.common import (
    registerSystemStatsMetric,
    writeSystemStatsMetric,
    incrementSystemStatsMetric,
)

# Схема метрики (создаёт свойство при первой записи)
registerSystemStatsMetric(
    "MyPlugin", "temperature",
    description="Sensor temperature",
    history=30,
)

# Запись в точке события (всегда track_stats=False)
writeSystemStatsMetric("MyPlugin", "temperature", 23.5)
incrementSystemStatsMetric("MyPlugin", "errors_total", 1)
```

`unregisterSystemStatsPlugin` — no-op (свойства остаются в объекте).

**Примеры в репозитории:** `plugins/Scheduler` (пул задач, цикл, dispatch), `plugins/xray` (пул БД, API latency).

#### Права доступа

`_merge_system_stats_permissions()` в `initPermissions()` задаёт `_permissions.object:SystemStats`: чтение для admin, запись/вызов методов запрещены (merge без перезаписи настроек администратора).

#### Инициализация

- `initSystemVar()` → `initSystemStats()` + `SystemVar.system_stats` (default `false`);
- при наличии пользователей → `initPermissions()` (в т.ч. права на `SystemStats`).

Тесты: `tests/test_system_stats.py`, `tests/test_object_manager.py`.

