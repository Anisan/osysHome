# Оптимизация записи на диск (Raspberry Pi / microSD)

Руководство по снижению износа microSD при работе osysHome на Raspberry Pi и аналогичных устройствах. Описаны параметры **ядра** (`config.yaml`). Оптимизация отдельных плагинов — отдельная задача.

Справочник ключей также обновлён в [configuration.ru.md](configuration.ru.md) и в комментариях `sample_config.yaml`.

## Зачем это нужно

Карты microSD чувствительны к частым мелким записям (логирование, fsync SQLite, INSERT в `history`). Ядро пишет на диск в основном через:

1. **Файловые логи** — `TimedRotatingFileHandler` (`app/logging_config.py`): по умолчанию отдельный файл на модуль + `errors.log`.
2. **BatchWriter** — периодический `commit` значений свойств и точек истории (`application.batch_writer_*`).
3. **SQLite** — WAL и `synchronous` определяют, как часто страницы сбрасываются на носитель.

Значения свойств в RAM coalesce’ятся (последнее значение на `value_id` за окно flush). История сохраняет **все** точки изменений — это намеренно. «Шумные» датчики нужно ограничивать на уровне свойства (`history: 0` или короткий срок хранения), а не скрытой потерей точек в ядре.

## Справочник параметров

### Секция `logging`

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `min_level` | `INFO` | Уровень логов при `application.debug: false`. При `debug: true` по умолчанию используется `DEBUG` (если не передан явный level в коде). |
| `file_enabled` | `true` | Писать файлы в `directory`. `false` — только console (удобно с systemd journal). |
| `console_enabled` | `true` | Вывод в stdout/stderr. |
| `directory` | `logs` | Каталог логов (относительный от корня проекта или абсолютный, например tmpfs). |
| `per_module_files` | `true` | `true` — `{module}.log`; `false` — один `app.log` + общий `errors.log`. |
| `memory_handler_capacity` | `0` | Буфер N записей в RAM перед сбросом на диск (`0` = сразу). При `ERROR+` буфер сбрасывается. |
| `backup_count` | `7` | Число ротированных копий (ротация в полночь). |

`security_audit.log` и `500.log` при `file_enabled: true` пишутся без MemoryHandler (ошибки и аудит не должны теряться в буфере). При `file_enabled: false` они идут в console.

### Секция `application` (BatchWriter)

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `batch_writer_flush_interval` | `0.5` | Интервал принудительного flush батча (секунды). Больше — реже commit, выше задержка сохранения. Все точки history в батче всё равно записываются. |
| `batch_writer_max_size` | `0` | Flush при достижении N записей в батче (`0` — только по таймеру). |

### Секция `database.sqlite` (только SQLite)

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `journal_mode` | `WAL` | Режим журнала (`WAL`, `DELETE`, …). |
| `synchronous` | не задан | `FULL` / `NORMAL` / `OFF`. Не задавать — оставить поведение SQLite после установки journal. Для Pi часто `NORMAL`. `OFF` — минимум fsync, риск при отключении питания. |
| `temp_store` | не задан | `DEFAULT` / `FILE` / `MEMORY`. |
| `cache_size` | не задан | Например `-65536` (~64 MiB page cache). |
| `mmap_size` | не задан | Размер mmap в байтах. |
| `wal_autocheckpoint` | не задан | Порог checkpoint WAL (страницы). |

Для PostgreSQL / MariaDB / MySQL приложение применяет те же `batch_writer_*` (меньше commit). Каталог данных СУБД и `synchronous_commit` / `innodb_flush_log_at_trx_commit` настраиваются **на стороне сервера**, не в osysHome.

### Прочее

- `cache.type: simple` — кеш в RAM; на Pi не используйте filesystem-backend на microSD.
- У частых датчиков уменьшайте дни хранения history свойства (или `0`) в объектах — меньше INSERT и чисток.

## Стратегии

### Мягкая

Цель: меньше шума в логах и чуть реже commit, почти без риска потери данных.

```yaml
application:
  debug: false
  batch_writer_flush_interval: 2.0
  batch_writer_max_size: 0

logging:
  min_level: WARNING
  file_enabled: true
  console_enabled: true
  directory: logs
  per_module_files: false
  memory_handler_capacity: 0
  backup_count: 7

database:
  db_name: 'app.db'
  sqlite:
    journal_mode: WAL
    synchronous: NORMAL
```

Риски: низкие. History полная.

### Средняя (рекомендуемый старт для Pi + microSD)

Цель: заметно меньше записи на SD при приемлемой диагностике.

```yaml
application:
  debug: false
  batch_writer_flush_interval: 5.0
  batch_writer_max_size: 200

logging:
  min_level: WARNING
  file_enabled: true
  console_enabled: true
  # Пример: mount -t tmpfs -o size=64M tmpfs /path/to/osysHome/logs
  directory: logs
  per_module_files: false
  memory_handler_capacity: 50
  backup_count: 3

database:
  db_name: 'app.db'
  sqlite:
    journal_mode: WAL
    synchronous: NORMAL
    temp_store: MEMORY
    cache_size: -65536
```

Плюс вручную: у частых датчиков `history: 0` или короткий срок хранения — иначе рост `history` покажет проблему, а не скроет её.

Риски: часть логов в RAM до flush / при tmpfs теряется при ребуте; больше задержка сохранения значений на диск.

### Жёсткая

Цель: минимум записи на microSD. Допустимо только при понимании рисков питания и слабой файловой диагностике.

```yaml
application:
  debug: false
  batch_writer_flush_interval: 10.0
  batch_writer_max_size: 500

logging:
  min_level: ERROR
  file_enabled: false   # логи в journald / console
  console_enabled: true
  directory: logs
  per_module_files: false
  memory_handler_capacity: 0
  backup_count: 1

database:
  # Лучше вынести файл с SD, например:
  # connection_string: 'sqlite:////mnt/usb/osyshome/app.db'
  db_name: 'app.db'
  sqlite:
    journal_mode: WAL
    synchronous: OFF
    temp_store: MEMORY
    cache_size: -65536
    wal_autocheckpoint: 2000
```

Обязательно: у «шумных» свойств `history: 0` или короткий срок; ИБП / корректный shutdown.

Риски: потеря недавних значений и WAL при внезапном отключении питания; почти нет файловых логов для разбора инцидентов.

## Готовый профиль: Raspberry Pi + microSD

Рекомендуемый старт — **средняя** стратегия выше. Скопируйте блок в свой `config.yaml`, затем при необходимости ужесточайте до жёсткой или ослабляйте до мягкой.

Чеклист инфраструктуры:

1. Логи на **tmpfs** (`logging.directory` → смонтированный tmpfs) или `file_enabled: false` + journald.
2. Файл SQLite по возможности на **USB/SSD**, не на той же microSD, что и ОС.
3. `cache.type: simple`.
4. `application.debug: false` в боевом режиме.
5. Не включать `database.sqlalchemy_echo` и тяжёлые `debug_tools` на Pi.

## PostgreSQL / MariaDB / MySQL

Параметры ядра `batch_writer_*` и `logging.*` действуют одинаково.

На стороне СУБД (подсказки админу, osysHome их не применяет):

- Каталог данных **не** на microSD.
- PostgreSQL: при осознанном риске — `synchronous_commit = off`, при необходимости `wal_compression`.
- MariaDB/MySQL: `innodb_flush_log_at_trx_commit = 2`, при необходимости `sync_binlog = 0`.

## Stop / restart и незаписанный батч

При увеличенном `batch_writer_flush_interval` в RAM может лежать до нескольких секунд значений/history. Ядро сбрасывает их через `app/graceful_shutdown.py`:

| Сценарий | Поведение |
|----------|-----------|
| `systemctl stop` / `restart` | SIGTERM → flush BatchWriter, логи, `onStop`, stop плагинов |
| Ctrl+C | SIGINT → то же |
| WebSocket «Restart» (`restart_system`) | перед `os._exit(1)` / `systemctl` / `docker restart` вызывается тот же flush (`os._exit` **не** вызывает `atexit`) |
| Внезапное питание / SIGKILL | flush невозможен — риск потери окна flush; не используйте `synchronous: OFF` без ИБП |

`TimeoutStopSec` в unit (сейчас 30 с в `deploy/systemd/osyshome.service`) должен быть больше типичного flush + остановки плагинов.

## Как оценить эффект

- Сравнить частоту ротации / размер файлов в `logs/` до и после.
- `iotop -ao`, `fatrace` (Linux) — активность записи процесса Python.
- Статистика BatchWriter в UI/API (если доступна): `flush_interval`, размер батча, число history inserts.
- Наблюдать стабильность после отключения питания на тестовой установке перед `synchronous: OFF`.

## Связанные файлы кода

- `app/logging_config.py` — handlers и уровни
- `app/configuration.py` — загрузка ключей
- `app/database.py` — SQLite PRAGMA
- `app/core/main/ObjectManager.py` — `BatchWriter`
- `app/graceful_shutdown.py` — flush при stop/restart
- `sample_config.yaml` — шаблон с комментариями
