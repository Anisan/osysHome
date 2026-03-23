## Troubleshooting (EN)

Common problems and how to debug them when running osysHome.

---

### 1. App does not start / crashes on startup

**Symptoms:**

- `python main.py` exits with an exception.
- Flask server does not listen on port `5000`.

**Checklist:**

1. **Python version**
   - Ensure you are using the same Python version as in `requirements.txt` (3.9+ recommended).
2. **Virtualenv / dependencies**
   - Did you run `pip install -r requirements.txt` in the active virtualenv?
3. **Config file**
   - Does `config.yaml` exist in the project root?
   - If not, copy `sample_config.yaml` and adjust minimal fields (`application.debug`, `database.*`).
4. **Database connectivity**
   - If using SQLite (default), check that `database.db_name` points to a writable location (e.g. `app.db` in project root).
   - For PostgreSQL/MySQL `connection_string`: check credentials, host, port and DB name.

**Where to look:**

- Console output from `python main.py`.
- Application logs (see `app/logging_config.py` for logger names and default formats).

---

### 2. Login page shows but you cannot log in

**Symptoms:**

- Login form loads, but credentials do not work.
- You are redirected back to the login page without clear message.

**Checklist:**

1. **First run admin user**
   - On the very first run, the system typically creates an initial admin user.
   - If you are unsure, stop the app, remove the DB file (for SQLite) and let it re‑initialize (development only).
2. **Users plugin**
   - Ensure the `osysHome-Users` plugin is installed (see README and Quickstart).
   - Without this plugin some user automation may be unavailable.

---

### 3. Blank or almost empty dashboard

**Symptoms:**

- You can log in and see the top menu, but the main panel has no widgets or data.

**Checklist:**

1. **Plugins**
   - Make sure recommended plugins are installed (Dashboard, Objects, Modules, Users, wsServer, Scheduler).
   - See `docs/QUICKSTART_selfhost.md` and the install scripts in `scripts/`.
2. **Objects and properties**
   - Check that you have created objects and properties via the admin UI.
   - Many dashboards only render widgets for existing configured objects.

---

### 4. Config or DB errors

**Symptoms:**

- Tracebacks mentioning SQLAlchemy, connection strings or missing tables.
- Messages like `OperationalError`, `ProgrammingError`, `table ... does not exist`.

**Checklist:**

1. **Database type and URL**
   - For SQLite, `database.db_name` should be something like `app.db`.
   - For PostgreSQL/MySQL, uncomment and fill in `connection_string` in `config.yaml` using the examples in `sample_config.yaml`.
2. **Permissions**
   - The user running osysHome must have permission to create/modify the DB file or connect to the DB server.
3. **Migrations**
   - If you changed enum formats or property params, make sure you followed the migration guides:
     - `MIGRATION_ENUM_VALUES.md`

---

### 5. Enum / property validation errors

**Symptoms:**

- Setting a property fails with `ValueError` messages like:
  - `Value ... is greater than maximum ...`
  - `Value ... is not aligned with step ...`
  - `Value ... is not in allowed values`
  - `Value ... is not in allowed enum values`

**Checklist:**

1. **Check `params` JSON**
   - Ensure that `min`, `max`, `step`, `allowed_values`, `enum_values`, `regexp` etc. are correct.
   - See `PARAMS_DOCUMENTATION.md` and `ENUM_TYPE_USAGE.md` for valid structures.
2. **Enum migration**
   - If you upgraded from an older version, ensure enums use the new `enum_values` format (`MIGRATION_ENUM_VALUES.md`).

---

### 6. Where to find logs

- Logging configuration is defined in `app/logging_config.py`.
- Typical loggers:
  - `main`, `flask`, `object`, plugin‑specific names, HTTP error loggers.
- In development, logs are usually printed to the console; in production you may redirect them to files via logging config.

---

## Диагностика проблем (RU)

Ниже приведены основные кейсы на русском языке. Подробные примеры и сообщения об ошибках смотрите в английской части выше.

### 1. Приложение не запускается

- Проверьте:
  - версию Python и наличие виртуального окружения;
  - что выполнено `pip install -r requirements.txt`;
  - что файл `config.yaml` существует и корректен;
  - настройки БД (`database.db_name` или `connection_string`).
- Смотрите стек‑трейс в консоли и настройки логирования в `app/logging_config.py`.

### 2. Не удаётся войти в систему

- Убедитесь, что:
  - система корректно инициализировала первого администратора;
  - установлены необходимые плагины, особенно `osysHome-Users`.

### 3. Пустая панель управления

- Чаще всего:
  - не установлены рекомендованные плагины (Dashboard, Objects, Users и др.);
  - ещё не созданы объекты и их свойства.

### 4. Ошибки конфигурации или БД

- Проверьте тип БД и строку подключения;
- Проверьте права на запись для файлов БД (SQLite) или доступ к серверу БД;
- При обновлении версии убедитесь, что выполнили необходимые миграции (например, `MIGRATION_ENUM_VALUES.md`).

### 5. Ошибки валидации свойств / enum

- Сообщения `ValueError` обычно указывают, какое ограничение нарушено (`min/max`, `step`, `allowed_values`, `enum_values`, `regexp`);
- Сверьтесь с `PARAMS_DOCUMENTATION.md` и `ENUM_TYPE_USAGE.md`.

