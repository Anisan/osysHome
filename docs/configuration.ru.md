# Конфигурация системы

Вся конфигурация osysHome хранится в файле `config.yaml` в корне проекта. Этот файл создаётся из шаблона `sample_config.yaml` при первоначальной настройке.

---

## Структура файла

```yaml
application:   # Основные параметры приложения
database:      # Настройки базы данных
cache:         # Настройки кеша
service:       # Управление сервисом
```

---

## Секция `application`

```yaml
application:
  default_language: 'ru'
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
```

| Параметр | Описание | По умолчанию |
|----------|----------|-------------|
| `default_language` | Язык интерфейса (`ru`, `en`) | `en` |
| `default_timezone` | Часовой пояс для отображения дат | `Europe/Moscow` |
| `secret_key` | Секретный ключ Flask для подписи сессий. **Обязательно смените!** | — |
| `debug` | Режим отладки: `true` — подробные ошибки в браузере, `false` — продакшен | `false` |
| `app_port` | Порт HTTP-сервера | `5000` |
| `env` | Окружение (`production` / `development`) | `production` |
| `pool_size` | Базовый размер пула потоков для выполнения методов | `20` |
| `pool_max_size` | Максимальный размер пула потоков | `100` |
| `pool_timeout_threshold` | Порог (сек.) для предупреждений о долгих задачах в пуле | `60.0` |
| `batch_writer_flush_interval` | Интервал (сек.) пакетной записи значений свойств в БД | `0.5` |
| `session_lifetime_days` | Время жизни сессии пользователя в днях | `31` |
| `http_request_timeout` | Таймаут HTTP-запросов (сек.) | `15` |

### Ограничение запросов (Rate Limiting)

```yaml
application:
  rate_limit:
    enabled: true
    default: '100 per minute'
    login: '5 per minute'
    api: '100 per minute'
```

| Параметр | Описание |
|----------|----------|
| `enabled` | Включить защиту от перебора/DoS |
| `default` | Общий лимит для всех маршрутов |
| `login` | Строгий лимит для страницы входа |
| `api` | Лимит для REST API |

### Безопасность сессий (для HTTPS)

```yaml
application:
  session_cookie_secure: true    # Только для HTTPS!
  session_cookie_samesite: 'Lax' # Защита от CSRF
```

> Оставьте `session_cookie_secure: false` при работе без HTTPS (локальное развёртывание).

---

## Секция `database`

### SQLite (по умолчанию, не требует установки)

```yaml
database:
  sqlalchemy_echo: false
  pool_size: 5
  db_name: 'app.db'
```

База данных создаётся автоматически в корне проекта при первом запуске.

### PostgreSQL (рекомендуется для продакшена)

```bash
# Установка драйвера
pip install psycopg2-binary
```

```yaml
database:
  sqlalchemy_echo: false
  pool_size: 20
  connection_string: 'postgresql://user:password@localhost/osyshome'
```

### MySQL / MariaDB

```bash
pip install PyMySQL
```

```yaml
database:
  connection_string: 'mysql+pymysql://user:password@localhost/osyshome'
```

| Параметр | Описание |
|----------|----------|
| `sqlalchemy_echo` | Выводить SQL-запросы в лог (только для отладки) |
| `pool_size` | Количество соединений в пуле SQLAlchemy |
| `db_name` | Имя файла SQLite (игнорируется, если задан `connection_string`) |
| `connection_string` | Строка подключения к PostgreSQL или MySQL |

---

## Секция `cache`

```yaml
cache:
  file_path: 'cache'
  type: 'simple'
  timeout: 300
```

| Параметр | Описание |
|----------|----------|
| `file_path` | Папка для файлового кеша (MP3-файлы TTS и другие данные) |
| `type` | Тип кеша: `simple` — in-memory, `filesystem` — файловый |
| `timeout` | Время жизни записи кеша в секундах |

---

## Секция `service`

```yaml
service:
  autorestart: false
  name: null
```

| Параметр | Описание |
|----------|----------|
| `autorestart` | Разрешить перезапуск сервиса из веб-интерфейса |
| `name` | Имя systemd-сервиса (например, `osyshome`) для управления из UI |

---

## Советы по безопасности

1. **Смените `secret_key`** — используйте случайную строку длиной 32+ символа:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Не коммитьте `config.yaml`** в публичный репозиторий — файл содержит пароли и секреты.

3. **Включите `session_cookie_secure: true`** если используете HTTPS/nginx-proxy.

4. **В продакшене** установите `debug: false` и `sqlalchemy_echo: false`.

5. **PostgreSQL** предпочтительнее SQLite при более чем 5–10 активных пользователях и высокой частоте обновлений устройств.
