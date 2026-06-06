# Установка и первый запуск

В этом разделе описан процесс установки osysHome с нуля — от клонирования репозитория до входа в веб-интерфейс.

---

## 1. Системные требования

- **Python 3.10 или новее**
- **Git**
- Операционная система: Linux, Windows 10+, macOS
- ~200 МБ свободного места на диске
- Доступ к сети (для плагинов, работающих с внешними API)

---

## 2. Получение исходного кода

```bash
git clone https://github.com/your-org/NextGetSmart.git
cd NextGetSmart
```

> Если вы скачали архив — просто распакуйте его и перейдите в папку проекта.

---

## 3. Создание виртуального окружения

Рекомендуется устанавливать зависимости в изолированное виртуальное окружение:

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

После активации в начале строки терминала появится `(venv)`.

---

## 4. Установка зависимостей

```bash
pip install -r requirements.txt
```

Установка занимает 1–5 минут в зависимости от скорости интернета. После завершения все основные библиотеки будут доступны.

---

## 5. Подготовка каталога плагинов

Создайте папку `plugins`, если она ещё не существует:

```bash
mkdir plugins
```

> Инструкции по установке конкретных плагинов находятся в директориях самих плагинов: `plugins/<PluginName>/README*.md`.

---

## 6. Создание конфигурационного файла

Скопируйте шаблон конфигурации:

**Linux / macOS:**
```bash
cp sample_config.yaml config.yaml
```

**Windows:**
```powershell
Copy-Item sample_config.yaml config.yaml
```

Затем откройте `config.yaml` в любом текстовом редакторе и проверьте основные параметры:

```yaml
application:
  default_language: 'ru'       # язык интерфейса
  default_timezone: 'Europe/Moscow'
  secret_key: 'замените-на-свой-секрет'  # обязательно смените!
  app_port: 5000

database:
  db_name: 'app.db'            # SQLite-база, создаётся автоматически
```

Подробно все параметры конфигурации описаны в разделе [Конфигурация](configuration.ru.md).

---

## 7. Первый запуск

```bash
python main.py
```

При первом запуске система автоматически:
1. Создаёт базу данных `app.db` (SQLite)
2. Применяет все миграции схемы
3. Загружает и инициализирует все активные плагины
4. Запускает веб-сервер на порту, указанном в `config.yaml` (по умолчанию **5000**)

В терминале вы увидите примерно такой вывод:

```
INFO  [main] Starting osysHome...
INFO  [PluginsHelper] Loading plugins...
INFO  [PluginName] Plugin initialized
...
INFO  [main] Running on http://0.0.0.0:5000
```

---

## 8. Вход в систему

Откройте браузер и перейдите по адресу:

```
http://localhost:5000
```

При первом запуске вам будет предложено создать учётную запись администратора. Введите логин и пароль — они будут сохранены в базе данных.

> После создания аккаунта вы попадёте в основной веб-интерфейс системы.

---

## 9. Что дальше

| Задача | Документ |
|--------|----------|
| Настроить параметры системы | [Конфигурация](configuration.ru.md) |
| Понять, что такое объекты и свойства | [Основные концепции](core-concepts.ru.md) |
| Настроить и использовать плагины | [Плагины](plugins.ru.md) |
| Создать автоматизацию | [Автоматизации](automation.ru.md) |

---

## Запуск как системный сервис (Linux)

Готовый unit-файл в репозитории:

```bash
sudo cp deploy/systemd/osyshome.service /etc/systemd/system/
# При необходимости измените User, WorkingDirectory, ExecStart
sudo systemctl daemon-reload
sudo systemctl enable --now osyshome
sudo systemctl status osyshome
```

Файл: [`deploy/systemd/osyshome.service`](../deploy/systemd/osyshome.service)

HTTPS, nginx, firewall: [Production-развёртывание](DEPLOY_PRODUCTION.ru.md).

В `config.yaml` укажите имя сервиса, если хотите управлять им из интерфейса:

```yaml
service:
  autorestart: true
  name: 'osyshome'
```

---

## Docker

Для продакшена рекомендуется запуск через Docker: образ ядра (`anisan1981/osyshome`) неизменяемый, все данные хранятся в volume на хосте.

```bash
# Без клонирования репозитория:
mkdir -p osyshome && cd osyshome
curl -fsSL https://raw.githubusercontent.com/Anisan/osysHome/master/docker/init-data.sh | bash
# отредактируйте config.yaml
docker compose up -d
```

Если репозиторий уже есть: `./docker/init-data.sh` и `docker compose up -d`.

Подробнее: раздел **Docker** в [QUICKSTART_selfhost.md](QUICKSTART_selfhost.md).

**GitHub Actions → Docker Hub:** secrets `DOCKERHUB_USERNAME` и `DOCKERHUB_TOKEN`. Сборка при push в **master** (тег `latest`), при push тега `v*` — semver (`v1.2.3`, `1.2`).
