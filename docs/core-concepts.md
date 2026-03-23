# Core Concepts

osysHome is built on an object-oriented model. Understanding five key entities will let you work with the system effectively: create devices, control them, and write automations.

---

## Model Overview

```
Class
  └── Object               ← a specific device instance
        ├── Property        ← a device parameter
        │     └── Value     ← the current value
        └── Method          ← executable Python code
```

This entire hierarchy is stored in the database and represents the real device landscape of your smart home.

---

## Class

A **Class** is a template (device type). Examples: "Lamp", "Thermometer", "Socket".

- Classes define which properties and methods objects of that type have.
- One class can be the **parent** of another (inheritance).
- Plugins create classes programmatically during initialization.

**Example classes:**

| Class name | Description |
|------------|-------------|
| `Lamp` | Smart light bulb |
| `Thermometer` | Temperature sensor |
| `Switch` | Toggle switch |
| `Presence` | Presence sensor |

---

## Object

An **Object** is a specific instance of a class — a real physical (or virtual) device in your home.

- Every object belongs to a class and inherits its properties and methods.
- Objects can be created via the web interface or programmatically from plugin code.

**Example:**

| Object name | Class | Description |
|-------------|-------|-------------|
| `LivingRoomLamp` | `Lamp` | Lamp in the living room |
| `BedroomSensor` | `Thermometer` | Temperature sensor in the bedroom |
| `KitchenSwitch` | `Switch` | Switch in the kitchen |

---

## Property

A **Property** is a named attribute of an object that stores a value.

Properties can be:

- Defined at the **class** level — inherited by all objects of that class
- Defined at the **object** level — unique to a specific device

### Property Types

| Type | Constant | Description |
|------|----------|-------------|
| Unset | `PropertyType.Empty` | Universal type |
| String | `PropertyType.String` | Text value |
| Integer | `PropertyType.Integer` | Whole number |
| Float | `PropertyType.Float` | Floating-point number |
| Boolean | `PropertyType.Boolean` | `True` / `False` |
| JSON | `PropertyType.Json` | Object or array |

### Property Parameters

| Parameter | Description |
|-----------|-------------|
| `name` | Unique property name within the object/class |
| `description` | Human-readable description |
| `history` | How many days to store history (0 = disabled) |
| `method_name` | Name of the method called when the value changes |

---

## Value

A **Value** is the current state of a property. Every change is recorded with a timestamp.

- Stored in the `Value` table in the database
- Written through the `BatchWriter` for performance
- History (the `History` table) is retained for the configured period when `history > 0`

---

## Method

A **Method** is a block of Python code attached to an object or class.

Methods are triggered:

- Automatically when a property value changes (if the property is configured to call a method)
- Manually via the API: `callMethod("ObjectName.methodName")`
- From the code of another method or automation

### Execution Context

Special variables available inside method code:

| Variable | Description |
|----------|-------------|
| `object` | The current object (read/write its properties) |
| `value` | The new value (when called from a property trigger) |
| `old_value` | The previous value |
| `args` | Additional arguments |

**Example method code:**

```python
# Method "onTemperatureChange" on the BedroomSensor object
if value > 25:
    say("The bedroom is too hot: " + str(value) + " degrees")
    setProperty("BedroomFan.state", True)
```

---

## Public API

Use the API from `app.core.lib.object` to work with objects from method code, plugins, and automations:

### Reading and Writing Properties

```python
from app.core.lib.object import getProperty, setProperty

# Get a property value
temp = getProperty("BedroomSensor.temperature")

# Set a property value
setProperty("LivingRoomLamp.state", True)
setProperty("Thermostat.target_temperature", 22.5)
```

### Calling Methods

```python
from app.core.lib.object import callMethod

callMethod("LivingRoomLamp.toggle")
callMethod("Alarm.activate", {"reason": "motion detected"})
```

### Creating Objects Programmatically

```python
from app.core.lib.object import addClass, addObject, addClassProperty
from app.core.lib.constants import PropertyType

# 1. Create a class
addClass("MySensor", description="My sensor")

# 2. Add a property to the class
addClassProperty(
    name="temperature",
    class_name="MySensor",
    description="Temperature",
    type=PropertyType.Float,
    history=30  # keep history for 30 days
)

# 3. Create an object
addObject("KitchenSensor", class_name="MySensor", description="Kitchen sensor")

# 4. Write a value
setProperty("KitchenSensor.temperature", 21.3)
```

### Helper Functions (`app.core.lib.common`)

```python
from app.core.lib.common import say, playSound, runCode

# Speak text (via the TTS plugin)
say("Welcome home!")

# Play a sound
playSound("notification.mp3")

# Execute arbitrary Python code
runCode("setProperty('Light.state', True)")
```

---

## Example: Full Device Lifecycle

```
1. z2m plugin detects a Zigbee sensor
        ↓
2. Creates class "ZigbeeSensor" (if it doesn't exist)
        ↓
3. Creates object "Hallway_Motion" with class "ZigbeeSensor"
        ↓
4. Sets property "occupancy" = True
        ↓
5. ObjectManager saves the value to the DB
        ↓
6. ObjectManager calls the linked method (if configured)
        ↓
7. All plugins with action="proxy" receive a notification
        ↓
8. Dashboard updates the widget in the browser via WebSocket
```

---

## Naming Conventions

Naming rules for objects and properties:

- Object and class names: `CamelCase` or `snake_case` (no spaces)
- Use dot notation to access a property: `ObjectName.propertyName`
- Names are case-sensitive: `lamp.state` ≠ `lamp.State`

```python
# Correct
setProperty("LivingRoomLamp.state", True)
getProperty("BedroomSensor.temperature")

# Incorrect — spaces in object names are not supported
setProperty("Living Room Lamp.state", True)  # error
```

---

## What's Next

The object model described here is the internal representation. To connect objects to real physical devices, read the next section: [Property–Plugin Binding](binding.md).
