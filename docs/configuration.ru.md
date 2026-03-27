# Конфигурация системы

Вся конфигурация osysHome хранится в файле `config.yaml` в корне проекта. Этот файл создаётся из шаблона `sample_config.yaml` при первоначальной настройке.

## Структура файла

```yaml
application:   # Основные параметры приложения
database:      # Настройки базы данных
debug_tools:   # Дополнительные тяжёлые инструменты отладки
cache:         # Настройки кеша
service:       # Управление сервисом
```

## Секция `application`

```yaml
application:
  default_language: 'en'
  default_timezone: 'Europe/Moscow'
  secret_key: 'your-secret-key-here'
  debug: false
  app_port: 5000
  env: 'production'
  pool_size: 20
  pool_max_size: 100
  pool_timeout_threshold: 60.0
  batch_writer_flush_interval: 0.5
  session_lifetime_days: 31
  http_request_timeout: 15
  session_cookie_secure: false
  session_cookie_samesite: 'Lax'
```

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `default_language` | Язык интерфейса по умолчанию (`en`, `ru`, `de` и т.д.) | `en` |
| `default_timezone` | Часовой пояс по умолчанию для отображения даты и времени | `Europe/Moscow` |
| `secret_key` | Секретный ключ Flask для сессий и токенов. В рабочей среде его нужно обязательно заменить. | `your-secret-key-here` |
| `debug` | Общий debug-режим приложения | `false` |
| `app_port` | HTTP-порт приложения | `5000` |
| `env` | Имя окружения, например `production` или `development` | `production` |
| `pool_size` | Базовый размер внутреннего пула рабочих потоков | `20` |
| `pool_max_size` | Максимальный размер пула рабочих потоков | `100` |
| `pool_timeout_threshold` | Порог в секундах, после которого задача в пуле считается долгой | `60.0` |
| `batch_writer_flush_interval` | Интервал принудительного сброса batched-записей в секундах | `0.5` |
| `session_lifetime_days` | Время жизни пользовательской сессии в днях | `31` |
| `http_request_timeout` | Таймаут исходящих HTTP-запросов в секундах | `15` |
| `session_cookie_secure` | Требовать HTTPS для cookie сессии | `false` |
| `session_cookie_samesite` | Политика SameSite для cookie сессии | `Lax` |

### Ограничение запросов (Rate Limiting)

```yaml
application:
  rate_limit:
    enabled: true
    default: '100 per minute'
    login: '5 per minute'
    api: '100 per minute'
```

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `enabled` | Включить защиту от brute-force и перегрузки | `true` |
| `default` | Общий лимит для всех маршрутов | `100 per minute` |
| `login` | Отдельный лимит для страницы входа | `5 per minute` |
| `api` | Лимит для API-маршрутов | `100 per minute` |

## Секция `database`

### Пример для SQLite

```yaml
database:
  sqlalchemy_echo: false
  pool_size: 20
  db_name: 'app.db'
```

SQLite-файл базы данных создаётся автоматически в корне проекта при первом запуске.

### Пример для PostgreSQL

```yaml
database:
  sqlalchemy_echo: false
  pool_size: 20
  connection_string: 'postgresql://user:password@localhost/osyshome'
```

### Пример для MySQL / MariaDB

```yaml
database:
  sqlalchemy_echo: false
  pool_size: 20
  connection_string: 'mysql+pymysql://user:password@localhost/osyshome'
```

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `sqlalchemy_echo` | Выводить SQL-запросы в лог | `false` |
| `pool_size` | Размер пула соединений SQLAlchemy | `20` |
| `db_name` | Имя SQLite-файла, используется если не задан `connection_string` | `app.db` |
| `connection_string` | Строка подключения к внешней БД PostgreSQL/MySQL/MariaDB | не задано |

## Секция `debug_tools`

Эта секция управляет дополнительными тяжёлыми инструментами отладки. Она отделена от `application.debug`, поэтому можно оставить обычный Flask debug включённым, но не активировать дорогие по производительности инструменты.

```yaml
debug_tools:
  enabled: false
  template_editor_enabled: false
  profiler_enabled: false
  profiler_dump_filename: 'dump.prof'
  intercept_redirects: false
  sqlalchemy_record_queries: false
```

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `enabled` | Включить Flask Debug Toolbar | `false` |
| `template_editor_enabled` | Включить редактор шаблонов в Debug Toolbar | `false` |
| `profiler_enabled` | Включить профилировщик HTTP-запросов | `false` |
| `profiler_dump_filename` | Имя файла для сохранения профиля | `dump.prof` |
| `intercept_redirects` | Перехватывать редиректы в Debug Toolbar | `false` |
| `sqlalchemy_record_queries` | Собирать статистику SQL-запросов для каждого HTTP-запроса | `false` |

## Секция `cache`

```yaml
cache:
  file_path: 'cache'
  type: 'simple'
  timeout: 300
```

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `file_path` | Путь к каталогу кеша | `cache` |
| `type` | Тип backend-а кеша, например `simple` | `simple` |
| `timeout` | Время жизни записи кеша в секундах | `300` |

## Секция `service`

```yaml
service:
  autorestart: false
  name: null
  docker_container: null
```

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `autorestart` | Разрешить встроенным операциям restart автоматически перезапускать сервис | `false` |
| `name` | Имя systemd-сервиса для операций управления и перезапуска | `null` |
| `docker_container` | Имя Docker-контейнера для операций управления и перезапуска | `null` |

## Советы по безопасности

1. Перед production обязательно замените `secret_key` на длинное случайное значение.
2. Не публикуйте `config.yaml` в открытых репозиториях.
3. При работе за HTTPS включайте `session_cookie_secure: true`.
4. В production держите `debug: false`, `sqlalchemy_echo: false` и `debug_tools.enabled: false`.
5. `sqlalchemy_record_queries` включайте только временно, когда ищете причину медленных страниц.
