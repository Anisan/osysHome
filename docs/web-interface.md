# Web Interface

osysHome is managed through a browser. The web interface is available at `http://your-server:5000` (the port is configured in `config.yaml`).

---

## Interface Structure

After logging in you will see a navigation menu with the following sections:

| Section | URL | Description |
|---------|-----|-------------|
| **Dashboard** | `/` | Main page with device widgets |
| **Objects** | `/admin/Objects` | Manage objects and classes |
| **Modules** | `/admin/Modules` | List of all plugins |
| **Scheduler** | `/admin/Scheduler` | Schedules and automation tasks |
| **Users** | `/admin/Users` | User management |
| **Backup** | `/admin/Backup` | Database backup |
| **Logs** | `/admin/Logs` | System log viewer |
| **Docs** | `/docs` | Documentation (this site) |
| **Object widget** | `/widget/object/<name>` | Standalone object widget page |
| **Plugin widget** | `/widget/plugin/<name>` | Standalone plugin widget page |

Each plugin adds its own menu item under the appropriate category.

---

## Dashboard

The Dashboard is the main page with customisable widgets.

### Widgets

Widgets are provided by plugins that declare the `widget` action. Default widgets include:

- **Current time and date**
- **Presence** (who is home)
- **Device state** (lamps, thermostats, etc.)
- **History graph** of property values
- **Upcoming tasks** from the Scheduler

### Customising the Dashboard

The order and set of widgets can be configured in **Admin → Dashboard**. Widgets can be dragged and hidden.

### Standalone widget page

A widget can be opened via a direct URL without the Dashboard chrome:

| URL | Content |
|-----|---------|
| `/widget/object/<name>` | HTML from the object template (`obj.render()`) |
| `/widget/plugin/<name>` | Plugin widget HTML (`plugin.widget()`) |
| `/widget/plugin/<name>/<widget_name>` | A specific plugin widget when several exist |

Access: any logged-in user (`user` / `editor` / `admin`), or that user's API key via `?apikey=...` or the `X-API-Key` header. For objects, read permission on the object is also checked; denied access returns 403.

The page is bare (no admin menu): the widget is wrapped in a full-viewport container (`.widget-page-root`). `say` / `notify` / `playsound` alerts are suppressed.

Fullscreen behaviour belongs in the widget itself (CSS/JS):

- CSS: parent `.widget-page-root` / `body.widget-page`;
- JS: `window.osysWidgetFullscreen === true`.

Live updates use WebSocket: `changeProperty` for properties and `changeObject` for a full object-template re-render.

---

## Objects Section

This is where you manage the full device hierarchy.

### Viewing Objects

- A list of all objects with their classes and descriptions
- Click an object to see its properties and current values
- Change history is available for properties with history recording enabled

### Creating an Object Manually

1. Go to **Admin → Objects**
2. Click the **"Add object"** button
3. Enter a name, select a class, and add a description
4. Click **"Save"**

After creating an object you can add properties and methods to it.

### Editing Properties

On the object page you can:

- Add a new property (**"+ Property"** button)
- Manually change the current property value
- Enable history recording
- Bind a method to a property (called on change)

### Editing Methods

Methods are Python code that executes inside the system. A code editor is available directly on the object page.

Built-in functions available in a method:

```python
# Get/set any object's property
value = getProperty("SomeSensor.temperature")
setProperty("SomeLamp.state", True)

# Call another object's method
callMethod("SomeLamp.toggle")

# Speak text
say("Message text")

# Play a sound
playSound("alert.mp3")
```

### Classes

The **"Classes"** tab shows all device templates. Here you can:

- Create a new class
- Add class-level properties and methods
- Define a template (HTML/Jinja2) for how objects of this class are displayed

Object and class templates can open content modals with arbitrary HTML via global `showContentModal` (history, settings, etc.). API and examples: [CONTENT_MODAL.md](CONTENT_MODAL.md).

---

## Modules Section (Plugins)

The `/admin/Modules` page lists all registered plugins.

For each plugin the following is shown:

- **Name and description**
- **Category** (Devices, App, System)
- **Version**
- **Status** (active / inactive)
- A button to open the plugin settings

### Enabling / Disabling a Plugin

1. Go to **Admin → Modules**
2. Find the plugin
3. Toggle the active switch
4. **Restart the system** — the change only takes effect after a restart

---

## Users Section

Manage system users.

### User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Full access to all settings |
| **User** | View Dashboard, limited control |

### Creating a User

1. Go to **Admin → Users**
2. Click **"Add user"**
3. Enter a login, password, and select a role
4. Click **"Save"**

---

## Logs Section

Centralised log viewer for the system.

- Each plugin writes to its own log file (`logs/<PluginName>.log`)
- Main system log: `logs/main.log`
- Error log: `logs/errors.log`
- Filter by plugin, level (INFO, WARNING, ERROR), and time

---

## Change History

Historical values are available for properties where `history > 0` (retention period in days).
Visualization and advanced analysis are provided by optional plugins documented in their own directories.

---

## REST API

osysHome provides a REST API for integration with external systems.

### Base URL

```
http://your-server:5000/api/
```

### Main Endpoints

> Update: in current core code API namespaces are mounted as `/api/object`, `/api/class`, `/api/property`, `/api/method`, `/api/utils`, `/api/plugins`.
> API key can be passed as query parameter `apikey` or header `X-API-Key`.

```http
GET  /api/objects               — list all objects
GET  /api/objects/{name}        — data for a specific object
GET  /api/objects/{name}/{prop} — current property value
POST /api/objects/{name}/{prop} — set a property value

GET  /api/classes               — list all classes
```

### Example Request (curl)

```bash
# Get a property value
curl http://localhost:5000/api/objects/LivingRoomLamp/state

# Set a value
curl -X POST http://localhost:5000/api/objects/LivingRoomLamp/state \
     -H "Content-Type: application/json" \
     -d '{"value": true}'
```

### Authentication

By default the API is only accessible to authenticated users. When integrating external systems use a session token or configure dedicated access permissions.

---

## WebSocket

The Dashboard receives real-time updates via a WebSocket connection. Plugins can push data to the browser with:

```python
self.sendDataToWebsocket("update", {"object": "LivingRoomLamp", "property": "state", "value": True})
```

This allows device state changes to be reflected instantly without reloading the page.
