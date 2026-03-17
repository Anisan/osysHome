# Property–Plugin Binding

Binding is the core mechanism in osysHome that connects a **virtual object** in the database to a **real physical device** managed by a plugin.

> **Important:** links are **always configured manually by the user** through the plugin's admin interface. The system never creates links automatically without user action.

---

## Why Binding Exists

In osysHome the object `LivingRoomLamp` is a database record. The physical lamp is controlled by a plugin (MQTT, Tuya, z2m, etc.). Binding creates the bridge between them:

- When the **lamp reports its state** → the plugin receives the device event and updates the object property in the system
- When the **system changes a value** (`setProperty("LivingRoomLamp.state", True)` from an automation) → ObjectManager notifies the plugin → the plugin sends a command to the physical device

```
Physical device
        ↕  (MQTT / Tuya / Zigbee / ESPHome / ...)
    Plugin
        ↕  (link configured by the user)
 Object.Property  ←→  ObjectManager  ←→  Automations / API / UI
```

---

## Two-Level Binding Architecture

Each plugin stores its binding configuration in its **own DB table**. The core system stores these bindings in the `Value.linked` field. Both levels are updated simultaneously when the user saves settings in the plugin's UI.

### Level 1 — Plugin table

Each plugin maintains its own table of records for physical entities (MQTT topics, Zigbee devices, Tuya DPS codes, etc.). Each record contains:

| Field | Description |
|-------|-------------|
| `linked_object` | Object name in osysHome (e.g., `LivingRoomLamp`) |
| `linked_property` | Object property name (e.g., `state`) |
| … | Plugin-specific fields (topic path, device ID, DPS code, etc.) |

This table is the source of truth for the plugin's configuration.

### Level 2 — `Value.linked` in the core

The `linked` field on a `Value` record is a comma-separated string of plugin names. ObjectManager uses it to know whom to notify when a value changes.

```
Value.linked = "Mqtt"        # on property change → call MqttPlugin.changeLinkedProperty(...)
Value.linked = "Mqtt,Tuya"   # notify two plugins
Value.linked = ""            # property is not linked to anything
```

### Keeping the levels in sync

When the user saves settings in the plugin's UI, the plugin itself calls `setLinkToObject`:

```python
# Inside the plugin's form handler — called when the user saves
from app.core.lib.object import setLinkToObject, removeLinkFromObject

# Remove the old link (if any)
removeLinkFromObject(old_object, old_property, "Mqtt")

# Register the new link
setLinkToObject(new_object, new_property, "Mqtt")
```

---

## How to Configure a Binding

### Example: MQTT

1. Go to **Admin → Mqtt**
2. Create or open a topic record
3. In **Linked object** enter the object name (e.g., `LivingRoomLamp`)
4. In **Linked property** enter the property name (e.g., `state`)
5. Click **Save**

After saving, the form automatically:

- Updates `Topic.linked_object` and `Topic.linked_property` in the MQTT table
- Calls `setLinkToObject("LivingRoomLamp", "state", "Mqtt")`
- Adds `"Mqtt"` to `Value.linked`

### Example: Zigbee2MQTT (z2m)

1. Go to **Admin → z2m**
2. Find the device and the desired property (expose)
3. Fill in **Linked object** and **Linked property** for that property row
4. Click **Save** — the plugin calls `setLinkToObject`

### Example: Tuya

1. Go to **Admin → Tuya** → select the device
2. In the DPS code table, set **Linked object** and **Linked property** for each code
3. Click **Save links** — the plugin calls `setLinkToObject` for each code

---

## How Binding Works at Runtime

### System → Physical device

```
Automation: setProperty("LivingRoomLamp.state", True)
        ↓
ObjectManager:
  1. Saves value to DB
  2. Calls the object method (if bound to property)
  3. Reads Value.linked  →  ["Mqtt"]
  4. For each plugin (except source):
       MqttPlugin.changeLinkedProperty("LivingRoomLamp", "state", True)
        ↓
Mqtt looks up its table: Topic where linked_object="LivingRoomLamp", linked_property="state"
        ↓
Mqtt publishes the value to the lamp's topic
        ↓
Physical lamp turns on
```

### Physical device → System

```
Lamp physically changes state → sends event to MQTT broker
        ↓
Mqtt plugin receives the message
        ↓
setProperty("LivingRoomLamp.state", True, source="Mqtt")
        ↓
ObjectManager:
  • Saves value
  • Value.linked = "Mqtt", but source = "Mqtt" → skip (loop prevention)
  • proxy plugins: notify
  • WebSocket: update Dashboard in browser
```

### Loop prevention

The `source` parameter is passed on every `setProperty` call. If the source matches a plugin name in `linked`, the callback to that plugin is skipped:

```python
# Physical device → Mqtt → system
setProperty("LivingRoomLamp.state", True, source="Mqtt")
# ObjectManager: Mqtt is in linked, but source="Mqtt" → skip → no loop
```

---

## The `changeLinkedProperty` Method

Every plugin that controls physical devices implements this method:

```python
def changeLinkedProperty(self, obj: str, prop: str, val):
    """
    Called by ObjectManager when a linked property has changed.
    obj  — object name (e.g., "LivingRoomLamp")
    prop — property name (e.g., "state")
    val  — new value
    """
    # Look up the record in the plugin's own table
    records = session.query(Topic).filter(
        Topic.linked_object == obj,
        Topic.linked_property == prop
    ).all()

    if not records:
        # Record was deleted by the user — remove the link
        removeLinkFromObject(obj, prop, self.name)
        return

    for rec in records:
        if not rec.readonly:
            self.mqttPublish(rec.path_write or rec.path, val)
```

The plugin looks up a record in **its own** table by the `(linked_object, linked_property)` pair. If no record is found (the user deleted the topic), the link is removed automatically.

---

## Full Example: Lamp via MQTT

**Step 1. User configures the topic in Admin → Mqtt:**

```
Title:           Living Room Lamp
Path:            home/living_room/lamp/state
Path write:      home/living_room/lamp/set
Linked object:   LivingRoomLamp
Linked property: state
```

After saving: `Value["LivingRoomLamp.state"].linked = "Mqtt"`

**Step 2. Automation turns the lamp on:**

```
setProperty("LivingRoomLamp.state", True)
→ Mqtt.changeLinkedProperty("LivingRoomLamp", "state", True)
→ publish("home/living_room/lamp/set", True)
→ Physical lamp turns on
```

**Step 3. Lamp confirms its state:**

```
Lamp publishes True to "home/living_room/lamp/state"
→ Mqtt: setProperty("LivingRoomLamp.state", True, source="Mqtt")
→ ObjectManager: skip Mqtt (source), notify proxy plugins, update UI
```
