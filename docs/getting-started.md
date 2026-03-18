# Installation & First Run

This section describes how to set up osysHome from scratch — from cloning the repository to logging into the web interface.

---

## 1. System Requirements

- **Python 3.10 or newer**
- **Git**
- OS: Linux, Windows 10+, macOS
- ~200 MB free disk space
- Network access (for plugins that work with external APIs)

---

## 2. Get the Source Code

```bash
git clone https://github.com/your-org/NextGetSmart.git
cd NextGetSmart
```

> If you downloaded an archive — simply extract it and navigate to the project folder.

---

## 3. Create a Virtual Environment

It is recommended to install dependencies in an isolated virtual environment:

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

After activation you will see `(venv)` at the beginning of your terminal prompt.

---

## 4. Install Dependencies

```bash
pip install -r requirements.txt
```

Installation takes 1–5 minutes depending on your internet speed. Once complete, all core libraries will be available.

---

## 5. Install Recommended Modules

Create the plugins directory and clone the recommended modules (same set as in `README.md`):

```bash
mkdir plugins
```

```bash
git clone https://github.com/Anisan/osysHome-Modules.git plugins/Modules
git clone https://github.com/Anisan/osysHome-Objects.git plugins/Objects
git clone https://github.com/Anisan/osysHome-Users.git plugins/Users
git clone https://github.com/Anisan/osysHome-Scheduler.git plugins/Scheduler
git clone https://github.com/Anisan/osysHome-wsServer.git plugins/wsServer
git clone https://github.com/Anisan/osysHome-Dashboard.git plugins/Dashboard
git clone https://github.com/Anisan/osysHome-Docs.git plugins/Docs
```

> If `plugins` already exists, the `mkdir plugins` step can be skipped.

---

## 6. Create the Configuration File

Copy the configuration template:

**Linux / macOS:**
```bash
cp sample_config.yaml config.yaml
```

**Windows:**
```powershell
Copy-Item sample_config.yaml config.yaml
```

Then open `config.yaml` in any text editor and review the essential settings:

```yaml
application:
  default_language: 'en'         # interface language
  default_timezone: 'Europe/Moscow'
  secret_key: 'replace-with-your-secret'  # must be changed!
  app_port: 5000

database:
  db_name: 'app.db'              # SQLite database, created automatically
```

All configuration parameters are described in detail in the [Configuration](configuration.md) section.

---

## 7. First Run

```bash
python main.py
```

On the first run the system automatically:
1. Creates the `app.db` database (SQLite)
2. Applies all schema migrations
3. Loads and initializes all active plugins
4. Starts the web server on the port defined in `config.yaml` (default **5000**)

You will see output similar to this in the terminal:

```
INFO  [main] Starting osysHome...
INFO  [PluginsHelper] Loading plugins...
INFO  [Scheduler] Plugin initialized
INFO  [Dashboard] Plugin initialized
...
INFO  [main] Running on http://0.0.0.0:5000
```

---

## 8. Log In

Open a browser and navigate to:

```
http://localhost:5000
```

On the first run you will be prompted to create an administrator account. Enter a login and password — they will be saved in the database.

> After creating the account you will be taken to the **Dashboard** — the main page of the system.

---

## 9. Next Steps

| Task | Document |
|------|----------|
| Configure system parameters | [Configuration](configuration.md) |
| Understand objects and properties | [Core Concepts](core-concepts.md) |
| Add a device | [Plugins](plugins.md) |
| Create an automation | [Automations](automation.md) |

---

## Running as a System Service (Linux)

If you want osysHome to start automatically when the server boots:

1. Create the file `/etc/systemd/system/osyshome.service`:

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

2. Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable osyshome
sudo systemctl start osyshome
```

3. Check the status:

```bash
sudo systemctl status osyshome
```

In `config.yaml`, specify the service name if you want to manage it from the UI:

```yaml
service:
  autorestart: true
  name: 'osyshome'
```
