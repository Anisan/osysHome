# Plugins

Plugins are the primary way to extend osysHome. Each plugin adds support for a new protocol, device, or feature.

---

## How the Plugin System Works

When osysHome starts:
1. It scans the `plugins/` directory — every subdirectory is treated as a plugin
2. It checks the database to see if the plugin is active
3. It dynamically imports the module and instantiates the main class
4. It calls `initialization()` and starts background threads (if needed)

Plugins marked as **inactive** are skipped entirely.

---

## Managing Plugins

### Viewing All Plugins

Go to **Admin → Modules**. The page shows a list of all plugins with:

- Name and description
- Category (Devices, App, System)
- Version
- Active status

### Enabling / Disabling

1. Find the plugin in the list
2. Click the toggle next to the plugin
3. **Restart the application** — changes only take effect after a restart

### Plugin Settings

Each plugin has its own settings page at `/admin/<PluginName>`.

---

## Plugin Overview

### System Plugins

Installed by default and provide core functionality.

| Plugin | Description |
|--------|-------------|
| **Scheduler** | Scheduled task execution (Cron) |
| **Objects** | Manage objects, classes, and properties |
| **Modules** | Display the plugin list |
| **Users** | User and permission management |
| **Backup** | Database backup |
| **Cleaner** | Clean up stale data and caches |
| **wsServer** | WebSocket server for real-time updates |
| **ConsoleMonitor** | View system logs in the browser |
| **Docs** | Built-in documentation (this site) |
| **Permissions** | Advanced access control |

### Device Plugins

| Plugin | Protocol | Supports |
|--------|----------|---------|
| **Mqtt** | MQTT | Any MQTT device, publish/subscribe |
| **z2m** | Zigbee2MQTT | Zigbee devices via Z2M broker |
| **Tuya** | Tuya Cloud / Local | Tuya/Smart Life devices (lamps, sockets, sensors) |
| **ESPHome** | ESPHome API | ESP8266/ESP32 devices with ESPHome firmware |
| **Bluetooth** | BLE | Bluetooth Low Energy sensors and devices |
| **Modbus** | Modbus RTU/TCP | Industrial meters and controllers |
| **OpenHASP** | MQTT | Control panels based on OpenHASP |
| **XiaomiHome** | Mi Home | Xiaomi devices via Mi Home cloud |
| **YandexDevices** | Yandex Smart Home | Yandex smart home devices |
| **Keenetic** | Keenetic API | Keenetic routers (network information) |
| **HisenseTv** | Hisense API | Hisense Smart TVs |
| **ThinQ** | LG ThinQ | LG home appliances |

### Application Plugins

| Plugin | Description |
|--------|-------------|
| **Dashboard** | Main page with widgets |
| **HistoryView** | Property value history charts |
| **Logs** | Web-based log file viewer |
| **Player** | Sound and music playback |
| **Storage** | File storage (images, configs) |
| **TelegramBot** | Notifications and commands via Telegram |
| **Todo** | Task list |
| **GoogleTTS** | Text-to-speech via Google Translate |
| **YandexTTS** | Text-to-speech via Yandex SpeechKit |
| **GpsTracker** | GPS coordinate tracking |
| **GoogleLocation** | Geolocation via Google API |
| **Friends2GIS** | Location map based on 2GIS |
| **AIAutomation** | AI-driven automations using ML |
| **AIRecommender** | Device control recommendations |

---

## Configuring Popular Plugins

### MQTT

MQTT is a universal smart home protocol. Most devices (sensors, lamps, switches) support MQTT.

**Setup:**
1. Go to **Admin → Mqtt**
2. Enter the broker address (e.g., `192.168.1.10`)
3. Port (default `1883`)
4. Username and password (if the broker requires them)
5. Click **"Save"** and restart

**Adding a device:**

- The plugin automatically creates objects when data is received from new topics
- Or manually bind a topic to an object property in the Mqtt settings

---

### Zigbee2MQTT (z2m)

Connects hundreds of Zigbee devices (motion sensors, temperature sensors, Philips Hue, IKEA lamps, etc.) via a Zigbee coordinator and the Z2M broker.

**Requirements:**

- A running [Zigbee2MQTT](https://www.zigbee2mqtt.io/) instance
- An MQTT broker (Mosquitto)

**Setup:**
1. Configure the **Mqtt** plugin (broker address)
2. Go to **Admin → z2m**
3. Enter the Z2M base topic (default `zigbee2mqtt`)
4. The plugin will automatically create objects for each device

---

### Tuya

Supports Tuya/Smart Life devices — lamps, sockets, humidifiers, robot vacuums.

**Setup:**
1. Obtain a `Client ID` and `Client Secret` from the [Tuya IoT Platform](https://iot.tuya.com/)
2. Go to **Admin → Tuya**
3. Enter the credentials
4. Click **"Sync devices"** — the system will fetch your device list

---

### Telegram Bot

Send notifications and control your home via Telegram.

**Setup:**
1. Create a bot with [@BotFather](https://t.me/BotFather) and get the token
2. Go to **Admin → TelegramBot**
3. Enter the bot token
4. Specify the list of allowed users (Telegram IDs)
5. Click **"Save"**

**Usage in automations:**
```python
# Send a Telegram message
setProperty("TelegramBot.message", "Motion sensor triggered in the hallway!")
```

---

### Google TTS / Yandex TTS

Text-to-speech — voice announcements through speakers.

**Google TTS:**
1. No API keys required — uses the free Google Translate TTS
2. Go to **Admin → GoogleTTS**
3. Specify the output device (speaker IP or audio output path)
4. Select a language (default `en`)

**Usage:**
```python
say("Good morning!")
say("Room temperature is " + str(getProperty("RoomSensor.temperature")) + " degrees")
```

---

## Plugin Dependencies

Some plugins require additional Python libraries listed in `plugins/<PluginName>/requirements.txt`.

Installing plugin dependencies:

```bash
pip install -r plugins/GoogleTTS/requirements.txt
pip install -r plugins/Mqtt/requirements.txt
```

Install for each plugin you need:

```bash
pip install -r plugins/Tuya/requirements.txt
pip install -r plugins/z2m/requirements.txt
```

---

## Installing a New Plugin

Plugins are distributed as code folders:

1. Place the plugin folder inside `plugins/`
2. Ensure the folder contains `__init__.py` with a class whose name matches the folder name
3. Install the plugin dependencies (if a `requirements.txt` is present)
4. Restart osysHome
5. The plugin will appear in **Admin → Modules** — enable and configure it
