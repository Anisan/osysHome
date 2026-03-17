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

## 5. Создание конфигурационного файла

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

## 6. Первый запуск

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
INFO  [Scheduler] Plugin initialized
INFO  [Dashboard] Plugin initialized
...
INFO  [main] Running on http://0.0.0.0:5000
```

---

## 7. Вход в систему

Откройте браузер и перейдите по адресу:

```
http://localhost:5000
```

При первом запуске вам будет предложено создать учётную запись администратора. Введите логин и пароль — они будут сохранены в базе данных.

> После создания аккаунта вы попадёте на **Dashboard** — главную страницу системы.

---

## 8. Что дальше

| Задача | Документ |
|--------|----------|
| Настроить параметры системы | [Конфигурация](configuration.ru.md) |
| Понять, что такое объекты и свойства | [Основные концепции](core-concepts.ru.md) |
| Добавить устройство | [Плагины](plugins.ru.md) |
| Создать автоматизацию | [Автоматизации](automation.ru.md) |

---

## Запуск как системный сервис (Linux)

Если вы хотите, чтобы osysHome запускался автоматически при старте сервера:

1. Создайте файл `/etc/systemd/system/osyshome.service`:

```ini
[Unit]
Description=osysHome Smart Home Platform
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/NextGetSmart
ExecStart=/path/to/NextGetSmart/venv/bin/python main.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

2. Активируйте и запустите сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl enable osyshome
sudo systemctl start osyshome
```

3. Проверьте статус:

```bash
sudo systemctl status osyshome
```

В `config.yaml` укажите имя сервиса, если хотите управлять им из интерфейса:

```yaml
service:
  autorestart: true
  name: 'osyshome'
```
