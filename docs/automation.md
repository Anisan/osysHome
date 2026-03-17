# Automations & Scheduler

Scheduler is a core osysHome plugin that executes Python code on a schedule or as a one-time job at a specified time. It is the primary tool for creating automations.

---

## What Is a Task

Each **task** contains:

- **Name** — a human-readable label (e.g., "Turn off lights at midnight")
- **Code** — the Python code that will run
- **Schedule** — when to run: a cron expression or a specific one-time datetime
- **Status** — active or paused

---

## Creating a Task

1. Go to **Admin → Scheduler**
2. Click **"Add task"**
3. Fill in the form:
   - **Name** — any descriptive label
   - **Code** — Python task code
   - **Cron** — a schedule expression (leave empty for a one-time run)
   - **Run time** — for a one-time run, specify date and time
4. Click **"Save"**

---

## Cron Syntax

Cron expressions define a repeating schedule:

```
┌─── seconds (0-59)       [optional]
│ ┌─── minutes (0-59)
│ │ ┌─── hours (0-23)
│ │ │ ┌─── day of month (1-31)
│ │ │ │ ┌─── month (1-12)
│ │ │ │ │ ┌─── day of week (0-7, 0 and 7 = Sunday)
│ │ │ │ │ │
* * * * * *
```

### Cron Expression Examples

| Expression | Meaning |
|------------|---------|
| `* * * * *` | Every minute |
| `0 * * * *` | Every hour (at the start of the hour) |
| `0 8 * * *` | Every day at 08:00 |
| `0 22 * * *` | Every day at 22:00 |
| `0 8 * * 1-5` | Weekdays at 08:00 |
| `0 8,18 * * *` | At 08:00 and 18:00 every day |
| `0 0 1 * *` | First day of each month at 00:00 |
| `*/15 * * * *` | Every 15 minutes |
| `*/30 * * * * *` | Every 30 seconds (6 fields — with seconds) |

> osysHome supports **6-field** cron expressions (seconds in the first field).

---

## Task Code

All built-in system functions are available inside task code.

### Controlling Devices

```python
# Turn on the living room lamp
setProperty("LivingRoomLamp.state", True)

# Set brightness
setProperty("LivingRoomLamp.brightness", 80)

# Turn off a group of lamps
for lamp in ["LivingRoomLamp", "HallLamp", "KitchenLamp"]:
    setProperty(lamp + ".state", False)
```

### Conditional Logic

```python
# Turn on the light only when someone is home
presence = getProperty("HomePresence.state")
hour = datetime.now().hour

if presence and 7 <= hour <= 23:
    setProperty("HallLamp.state", True)
else:
    setProperty("HallLamp.state", False)
```

### Notifications

```python
# Voice notification via TTS
say("Good morning! Today is " + str(datetime.now().strftime("%A")))

# Telegram notification (if TelegramBot plugin is configured)
# setProperty("TelegramBot.message", "Home temperature: " + str(getProperty("HomeSensor.temperature")))
```

### Working with Multiple Objects

```python
# Check all motion sensors
motion_sensors = ["HallMotion", "KitchenMotion", "LivingRoomMotion"]
any_motion = any(getProperty(s + ".occupancy") for s in motion_sensors)

if not any_motion:
    # Nobody home — turn everything off
    setProperty("MainSwitch.state", False)
    say("All devices turned off")
```

---

## Available Functions in Task Code

| Function | Description |
|----------|-------------|
| `getProperty("Obj.prop")` | Get the current property value |
| `setProperty("Obj.prop", value)` | Set a property value |
| `callMethod("Obj.method")` | Call an object method |
| `say("text")` | Speak text via TTS |
| `playSound("file.mp3")` | Play an audio file |
| `runCode("code")` | Execute a code string |
| `datetime` | `datetime` object from the standard library |
| `log("message")` | Write to the task log |

---

## Automation Examples

### Morning Routine

```python
# Weekdays at 07:00: 0 7 * * 1-5
say("Good morning! Time to wake up.")
setProperty("BedroomLamp.state", True)
setProperty("BedroomLamp.brightness", 30)  # soft light
setProperty("KettleSocket.state", True)     # turn on the kettle
```

### Evening Routine

```python
# Every day at 22:00: 0 22 * * *
temp = getProperty("OutdoorSensor.temperature")
if temp is not None and temp < 15:
    say("It's cold outside, " + str(round(temp)) + " degrees. Are the windows closed?")
setProperty("LivingRoomLamp.brightness", 20)  # dim the lights
```

### Night Mode

```python
# Every day at 23:30: 30 23 * * *
devices_off = ["LivingRoomLamp", "KitchenLamp", "HallLamp", "TVSocket"]
for device in devices_off:
    setProperty(device + ".state", False)

# Night light to minimum
setProperty("BedroomLamp.brightness", 5)
```

### Boiler Temperature Alert

```python
# Every 5 minutes: */5 * * * *
temp = getProperty("BoilerSensor.temperature")
if temp is not None and temp < 40:
    say("Warning! Boiler is cooling down: " + str(temp) + " degrees")
    setProperty("AlertLight.state", True)
```

### Presence-Based Energy Saving

```python
# Every 10 minutes: */10 * * * *
presence = getProperty("HomePresence.state")
if not presence:
    # Nobody home — minimum mode
    setProperty("Thermostat.target_temp", 16)
    setProperty("AllLights.state", False)
else:
    # Someone home — comfort mode
    setProperty("Thermostat.target_temp", 21)
```

---

## One-Time Tasks

Leave the **Cron** field empty and the task will run **once** at the specified time.

This is useful for:

- Delayed execution ("turn off in 2 hours")
- Reminders
- Testing code

---

## Creating Tasks Dynamically from Code

You can create tasks programmatically from object methods or other tasks:

```python
from app.core.lib.common import addCronJob, clearTimeout

# Create a one-time task (like setTimeout)
# Turn off the lamp in 30 minutes
addCronJob(
    name="TurnOffLamp",
    code="setProperty('LivingRoomLamp.state', False)",
    runtime=datetime.now() + timedelta(minutes=30)
)

# Cancel the task
clearTimeout("TurnOffLamp")
```

---

## Task Monitoring

The **Admin → Scheduler** → **Monitoring** tab shows:

- Current thread pool status
- Task execution statistics
- Tasks currently running
- Errors from recent runs

This information helps you find hung tasks or tasks that are failing.
