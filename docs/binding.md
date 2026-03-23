# Property–Plugin Binding

Binding is the core mechanism in osysHome that connects a **virtual object** in the database to a **real physical device** managed by a plugin.

> **Important:** links are **always configured manually by the user** through the plugin's admin interface. The system never creates links automatically without user action.

---

## Why Binding Exists

In osysHome the object `LivingRoomLamp` is a database record. The physical lamp is controlled by an integration plugin. Binding creates the bridge between them:

- When the **lamp reports its state** → the plugin receives the device event and updates the object property in the system
- When the **system changes a value** (`setProperty("LivingRoomLamp.state", True)` from an automation) → ObjectManager notifies the plugin → the plugin sends a command to the physical device

```
Physical device
        ↕  (integration protocol handled by plugin)
    Plugin
        ↕  (link configured by the user)
 Object.Property  ←→  ObjectManager  ←→  Automations / API / UI
```

---

## Two-Level Binding Architecture

Each plugin stores its binding configuration in its **own DB table**. The core system stores these bindings in the `Value.linked` field. Both levels are updated simultaneously when the user saves settings in the plugin's UI.

### Level 1 — Plugin table

Each plugin maintains its own table of records for physical entities (addresses, identifiers, paths, etc.). Each record contains:

| Field | Description |
|-------|-------------|
| `linked_object` | Object name in osysHome (e.g., `LivingRoomLamp`) |
| `linked_property` | Object property name (e.g., `state`) |
| … | Plugin-specific fields (topic path, device ID, DPS code, etc.) |

This table is the source of truth for the plugin's configuration.

### Level 2 — `Value.linked` in the core

The `linked` field on a `Value` record is a comma-separated string of plugin names. ObjectManager uses it to know whom to notify when a value changes.

```
Value.linked = "PluginA"         # on property change → call PluginA.changeLinkedProperty(...)
Value.linked = "PluginA,PluginB" # notify two plugins
Value.linked = ""            # property is not linked to anything
```

### Keeping the levels in sync

When the user saves settings in the plugin's UI, the plugin itself calls `setLinkToObject`:

```python
# Inside the plugin's form handler — called when the user saves
from app.core.lib.object import setLinkToObject, removeLinkFromObject

# Remove the old link (if any)
removeLinkFromObject(old_object, old_property, "PluginA")

# Register the new link
setLinkToObject(new_object, new_property, "PluginA")
```

---

## How to Configure a Binding

The exact UI and storage fields depend on the plugin implementation, but the core flow is always the same:

1. Open a plugin's settings page in Admin UI
2. Select a physical entity in that plugin
3. Set **Linked object** and **Linked property**
4. Save settings

After saving, the plugin:

- Stores `linked_object` and `linked_property` in its own table
- Calls `setLinkToObject(...)` in the core
- Updates `Value.linked` for the target property

---

## How Binding Works at Runtime

### System → Physical device

```
Automation: setProperty("LivingRoomLamp.state", True)
        ↓
ObjectManager:
  1. Saves value to DB
  2. Calls the object method (if bound to property)
  3. Reads Value.linked  →  ["PluginA"]
  4. For each plugin (except source):
       PluginA.changeLinkedProperty("LivingRoomLamp", "state", True)
        ↓
PluginA looks up its table by linked object/property
        ↓
PluginA sends the value to the physical device endpoint
        ↓
Physical lamp turns on
```

### Physical device → System

```
Lamp physically changes state → sends event to plugin transport
        ↓
PluginA receives the message
        ↓
setProperty("LivingRoomLamp.state", True, source="PluginA")
        ↓
ObjectManager:
  • Saves value
  • Value.linked = "PluginA", but source = "PluginA" → skip (loop prevention)
  • proxy plugins: notify
  • WebSocket: update Dashboard in browser
```

### Loop prevention

The `source` parameter is passed on every `setProperty` call. If the source matches a plugin name in `linked`, the callback to that plugin is skipped:

```python
# Physical device → PluginA → system
setProperty("LivingRoomLamp.state", True, source="PluginA")
# ObjectManager: PluginA is in linked, but source="PluginA" → skip → no loop
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
            self.send_to_device(rec, val)
```

The plugin looks up a record in **its own** table by the `(linked_object, linked_property)` pair. If no record is found, the link is removed automatically.

---

## Full Example: Generic Integration Plugin

**Step 1. User creates a binding in plugin settings:**

```
Entity ID:        living_room_lamp
Linked object:    LivingRoomLamp
Linked property:  state
```

After saving: `Value["LivingRoomLamp.state"].linked = "PluginA"`

**Step 2. Automation turns the lamp on:**

```
setProperty("LivingRoomLamp.state", True)
→ PluginA.changeLinkedProperty("LivingRoomLamp", "state", True)
→ plugin transport sends command to device
→ Physical lamp turns on
```

**Step 3. Device reports state back:**

```
Device reports True
→ PluginA: setProperty("LivingRoomLamp.state", True, source="PluginA")
→ ObjectManager: skip PluginA (source), notify proxy plugins, update UI
```
