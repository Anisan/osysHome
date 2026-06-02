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

If you prefer, you can install the same recommended set manually (same as `README.md`):

```bash
git clone https://github.com/Anisan/osysHome-Modules.git plugins/Modules
git clone https://github.com/Anisan/osysHome-Objects.git plugins/Objects
git clone https://github.com/Anisan/osysHome-Users.git plugins/Users
git clone https://github.com/Anisan/osysHome-Scheduler.git plugins/Scheduler
git clone https://github.com/Anisan/osysHome-wsServer.git plugins/wsServer
git clone https://github.com/Anisan/osysHome-Dashboard.git plugins/Dashboard
git clone https://github.com/Anisan/osysHome-Docs.git plugins/Docs
```

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

### 8. Docker (recommended for production)

The core image is published on [Docker Hub](https://hub.docker.com/r/anisan1981/osyshome). Runtime data (config, logs, cache, files, plugins, database) is stored **outside** the container via volumes.

#### Prepare host directories

If you already cloned the repository:

```bash
# Linux/macOS
./docker/init-data.sh

# Windows (PowerShell)
.\docker\init-data.ps1
```

Without cloning the full repository (downloads only init script and required files):

```bash
mkdir -p osyshome && cd osyshome
curl -fsSL https://raw.githubusercontent.com/Anisan/osysHome/master/docker/init-data.sh | bash
```

```powershell
mkdir osyshome -Force; cd osyshome
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/Anisan/osysHome/master/docker/init-data.ps1" -OutFile init-data.ps1
.\init-data.ps1
```

The script creates `config.yaml`, `docker-compose.yml`, data directories, and `app.db`.

Edit `config.yaml` before first start.

#### Run with Docker Compose

```bash
docker compose up -d
```

Open `http://localhost:5000` (image `anisan1981/osyshome:latest`).

GitHub Actions builds and publishes the image on push to **master** (tag `latest`).

#### Pull prebuilt image (without local build)

```bash
export OSYSHOME_IMAGE=anisan1981/osyshome:latest
docker compose pull
docker compose up -d
```

#### Volume layout

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `./config.yaml` | `/app/config.yaml` | User configuration |
| `./logs/` | `/app/logs/` | Application logs |
| `./cache/` | `/app/cache/` | File cache |
| `./files/` | `/app/files/` | Uploaded files |
| `./plugins/` | `/app/plugins/` | Plugins (update via `git pull` on host) |
| `./app.db` | `/app/app.db` | SQLite database |

#### Updating

- **Core**: `docker compose pull && docker compose up -d`
- **Plugins**: update repositories in `./plugins/` on the host, then restart the container.
- **Plugin pip dependencies**: included in the image at build time. If a plugin adds new Python packages, rebuild and publish a new core image.

#### Build locally

```bash
docker build -t anisan1981/osyshome:local .
docker run --rm -p 5000:5000 \
  -v "$(pwd)/config.yaml:/app/config.yaml" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/cache:/app/cache" \
  -v "$(pwd)/files:/app/files" \
  -v "$(pwd)/plugins:/app/plugins" \
  -v "$(pwd)/app.db:/app/app.db" \
  anisan1981/osyshome:local
```

On first start, if `plugins/` is empty, recommended plugins are cloned automatically. If `config.yaml` is missing or empty, it is created from `sample_config.yaml`.

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

Если удобнее, можете поставить тот же набор вручную (как в `README.md`):

```bash
git clone https://github.com/Anisan/osysHome-Modules.git plugins/Modules
git clone https://github.com/Anisan/osysHome-Objects.git plugins/Objects
git clone https://github.com/Anisan/osysHome-Users.git plugins/Users
git clone https://github.com/Anisan/osysHome-Scheduler.git plugins/Scheduler
git clone https://github.com/Anisan/osysHome-wsServer.git plugins/wsServer
git clone https://github.com/Anisan/osysHome-Dashboard.git plugins/Dashboard
git clone https://github.com/Anisan/osysHome-Docs.git plugins/Docs
```

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

### 8. Docker (рекомендуется для продакшена)

Образ ядра публикуется на [Docker Hub](https://hub.docker.com/r/anisan1981/osyshome). Данные (конфиг, логи, кеш, файлы, плагины, БД) хранятся **вне контейнера** через volume.

#### Подготовка каталогов на хосте

Если репозиторий уже склонирован:

```bash
# Linux/macOS
./docker/init-data.sh

# Windows (PowerShell)
.\docker\init-data.ps1
```

Без клонирования всего репозитория (скачивает только init-скрипт и нужные файлы):

```bash
mkdir -p osyshome && cd osyshome
curl -fsSL https://raw.githubusercontent.com/Anisan/osysHome/master/docker/init-data.sh | bash
```

```powershell
mkdir osyshome -Force; cd osyshome
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/Anisan/osysHome/master/docker/init-data.ps1" -OutFile init-data.ps1
.\init-data.ps1
```

Скрипт создаёт `config.yaml`, `docker-compose.yml`, каталоги данных и `app.db`.

Отредактируйте `config.yaml` перед первым запуском.

#### Запуск через Docker Compose

```bash
docker compose up -d
```

Откройте `http://localhost:5000` (образ `anisan1981/osyshome:latest`).

Сборка образа в GitHub Actions — при push в ветку **master** (тег `latest`).

#### Готовый образ (без локальной сборки)

```bash
export OSYSHOME_IMAGE=anisan1981/osyshome:latest
docker compose pull
docker compose up -d
```

#### Что монтируется

| Путь на хосте | Путь в контейнере | Назначение |
|---------------|-------------------|------------|
| `./config.yaml` | `/app/config.yaml` | Конфигурация |
| `./logs/` | `/app/logs/` | Логи |
| `./cache/` | `/app/cache/` | Кеш |
| `./files/` | `/app/files/` | Файлы |
| `./plugins/` | `/app/plugins/` | Плагины |
| `./app.db` | `/app/app.db` | SQLite |

#### Обновление

- **Ядро**: `docker compose pull && docker compose up -d`
- **Плагины**: обновите репозитории в `./plugins/` на хосте и перезапустите контейнер.
- **pip-зависимости плагинов**: ставятся при сборке образа. Если плагину нужны новые пакеты — нужна пересборка и публикация нового образа ядра.

#### Локальная сборка

```bash
docker build -t anisan1981/osyshome:local .
docker run --rm -p 5000:5000 \
  -v "$(pwd)/config.yaml:/app/config.yaml" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/cache:/app/cache" \
  -v "$(pwd)/files:/app/files" \
  -v "$(pwd)/plugins:/app/plugins" \
  -v "$(pwd)/app.db:/app/app.db" \
  anisan1981/osyshome:local
```

При первом запуске, если `plugins/` пуст, рекомендованные плагины клонируются автоматически. Если `config.yaml` отсутствует или пуст — создаётся из `sample_config.yaml`.

### 9. Что дальше

- Пункт меню в веб‑интерфейсе **Docs** → статическая документация (`docs/index.html`).
- В репозитории: `docs/INDEX.md` — обзор всех разделов.
- Архитектура: `docs/ARCHITECTURE.md`
- Плагины: `docs/PLUGINS_guide.md`

