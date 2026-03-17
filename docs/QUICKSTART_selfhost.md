## Quickstart for self‑host users (EN)

This guide helps you go from `git clone` to a working osysHome web UI in about 10–15 minutes.

### 1. Requirements

- Python **3.9+** (recommended)
- Git
- OS: Linux, Windows 10+, or any system that supports Python and Docker (optional)
- 512 MB RAM+ (more recommended for plugins)

### 2. Clone and install

```bash
git clone https://github.com/Anisan/osysHome.git
cd osysHome
```

Create and activate a virtual environment:

```bash
# Linux
python3 -m venv venv
source venv/bin/activate

# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Install recommended plugins (one‑liner)

These plugins provide core functionality (objects, users, dashboard, scheduler, websockets, etc.).

#### Linux/macOS

```bash
mkdir -p plugins
./scripts/install_recommended_plugins.sh
```

#### Windows (PowerShell)

```powershell
mkdir plugins -ErrorAction SilentlyContinue
.\scripts\install_recommended_plugins.ps1
```

You can also run the `git clone` commands from `Install recommended modules` section in `README.md` manually.

### 4. Create minimal config

Copy sample config and adjust it:

```bash
# Linux
cp sample_config.yaml config.yaml

# Windows (PowerShell)
Copy-Item sample_config.yaml config.yaml
```

Open `config.yaml` in any editor and check key sections (see also comments in the file):

- `application.default_language` — default UI language (`en`, `ru`, `de` if translations exist)
- `application.debug` — set `false` for production, `true` while experimenting
- `database.db_name` — SQLite database file name (default `app.db` in project root)

Minimal local configuration typically keeps:

```yaml
application:
  debug: true
database:
  db_name: 'app.db'
```

For PostgreSQL/MySQL see commented `connection_string` examples in `sample_config.yaml`.

### 5. Run osysHome

From the project root:

```bash
# Linux
python3 main.py

# Windows
python main.py
```

By default the app listens on port `5000`:

- Open `http://localhost:5000` in your browser.

### 6. First login and admin user

- On the first start, osysHome initializes system objects.
- When you open the web UI for the first time:
  - You will be prompted to create an administrator account (login/password).
  - This account will have full access to the control panel.

### 7. First useful setup (objects and dashboard)

1. Log in with the admin account.
2. Open **Control panel** (`/admin`).
3. Ensure the **Dashboard** plugin is installed and enabled (from the recommended set).
4. Use the **Modules/Objects** pages (from plugins) to:
   - Create a **virtual switch** or **sensor** object.
   - Add a few properties (e.g. `state` as `bool`, `brightness` as `int`).
5. Open the main panel (dashboard) and verify that widgets are shown.

For more details on properties and validation params, see:

- `PARAMS_DOCUMENTATION.md`
- `ENUM_TYPE_USAGE.md`

### 8. Docker (optional lazy path)

You can also run osysHome in Docker:

```bash
sudo docker build -t osyshome .
sudo docker run -d --network host -p 5000:5000 osyshome
```

For persistent data, mount volumes for `config.yaml` and `app.db` (or your external DB).

### 9. Where to go next

- Web UI top menu → **Docs** — open `docs/index.html` or this repo’s `docs/INDEX.md`.
- Learn architecture: `docs/ARCHITECTURE.md`
- Learn about plugins: `docs/PLUGINS_guide.md`

---

## Быстрый старт для self‑host пользователей (RU)

Это краткое руководство поможет за 10–15 минут дойти от `git clone` до работающего веб‑интерфейса osysHome.

### 1. Требования

- Python **3.9+** (рекомендуется)
- Git
- ОС: Linux, Windows 10+ или любая, где работает Python и Docker (опционально)
- От ~512 МБ ОЗУ (больше — лучше, особенно с плагинами)

### 2. Клонирование и установка

```bash
git clone https://github.com/Anisan/osysHome.git
cd osysHome
```

Создайте и активируйте виртуальное окружение:

```bash
# Linux
python3 -m venv venv
source venv/bin/activate

# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Установите зависимости:

```bash
pip install -r requirements.txt
```

### 3. Установка рекомендованных модулей (one‑liner)

Эти модули дают основные возможности: объекты, пользователи, панель, планировщик, WebSocket и т.п.

#### Linux/macOS

```bash
mkdir -p plugins
./scripts/install_recommended_plugins.sh
```

#### Windows (PowerShell)

```powershell
mkdir plugins -ErrorAction SilentlyContinue
.\scripts\install_recommended_plugins.ps1
```

Также вы можете вручную выполнить `git clone` команды из секции `Install recommended modules` в `README.md`.

### 4. Создание минимальной конфигурации

Скопируйте пример конфига и отредактируйте:

```bash
# Linux
cp sample_config.yaml config.yaml

# Windows (PowerShell)
Copy-Item sample_config.yaml config.yaml
```

Откройте `config.yaml` и проверьте ключевые секции (подробные комментарии есть внутри файла):

- `application.default_language` — язык интерфейса (`en`, `ru`, `de`, если есть переводы)
- `application.debug` — `false` для продакшена, `true` для экспериментов
- `database.db_name` — имя файла БД SQLite (по умолчанию `app.db` в корне проекта)

Минимальная локальная конфигурация обычно выглядит так:

```yaml
application:
  debug: true
database:
  db_name: 'app.db'
```

Для PostgreSQL/MySQL используйте примеры `connection_string` в `sample_config.yaml`.

### 5. Запуск osysHome

Из корня проекта:

```bash
# Linux
python3 main.py

# Windows
python main.py
```

По умолчанию приложение слушает порт `5000`:

- Откройте в браузере `http://localhost:5000`.

### 6. Первый вход и администратор

- При первом запуске osysHome инициализирует системные объекты.
- При первом открытии веб‑интерфейса:
  - Вам предложат создать администратора (логин/пароль).
  - Этот пользователь будет иметь полный доступ к панели управления.

### 7. Первый полезный сценарий (объекты и панель)

1. Войдите под администратором.
2. Откройте **Control panel** (`/admin`).
3. Убедитесь, что установлен и включён плагин **Dashboard** (из рекомендованных модулей).
4. Через страницы **Modules/Objects** (из плагинов):
   - Создайте **виртуальный выключатель** или **датчик**.
   - Добавьте несколько свойств (например, `state` как `bool`, `brightness` как `int`).
5. Откройте главную панель (dashboard) и проверьте, что виджеты отображаются.

Подробнее о свойствах и параметрах валидации:

- `PARAMS_DOCUMENTATION.md`
- `ENUM_TYPE_USAGE.md`

### 8. Docker (ленивый вариант)

Можно запустить osysHome в Docker:

```bash
sudo docker build -t osyshome .
sudo docker run -d --network host -p 5000:5000 osyshome
```

Для постоянного хранения данных примонтируйте тома под `config.yaml` и БД (`app.db` или внешняя БД).

### 9. Что дальше

- Пункт меню в веб‑интерфейсе **Docs** → статическая документация (`docs/index.html`).
- В репозитории: `docs/INDEX.md` — обзор всех разделов.
- Архитектура: `docs/ARCHITECTURE.md`
- Плагины: `docs/PLUGINS_guide.md`

