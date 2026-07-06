# MCP Plugin Management

Optional contract for exposing plugin configuration and entities to MCPServer.

## Overview

Device and app plugins store their own records in plugin tables. MCPServer uses a
uniform gateway tool `osys_plugin` that calls optional `mcp_*` methods on
[`BasePlugin`](../app/core/main/BasePlugin.py).

Binding with osysHome objects is described in [binding.ru.md](./binding.ru.md).
Property-level links must be synchronized through
[`plugin_binding.py`](../app/core/lib/plugin_binding.py).

## Collections

Each plugin declares collections in `mcp_capabilities()`:

| Field | Description |
|-------|-------------|
| `id` | Collection identifier (`topics`, `commands`, …) |
| `title` | Human-readable title |
| `binding_mode` | `none`, `object`, or `property` |
| `writable` | Whether CRUD is allowed |
| `has_code` | Whether entities contain Python `code` |

## Binding modes

| Mode | Example | Core sync |
|------|---------|-----------|
| `none` | TelegramBot commands | none |
| `object` | GpsTracker devices | validate object exists |
| `property` | Mqtt topics | `setLinkToObject` / `removeLinkFromObject` |

## MCP tools (MCPServer)

- `osys_list_plugins`
- `osys_get_plugin_config` / `osys_update_plugin_config`
- `osys_manage_property_links`
- `osys_plugin` gateway (`action`, `plugin`, `args`)

## Reference implementations

- **Mqtt** — `topics` collection, `binding_mode: property`
- **TelegramBot** — `commands`, `events`, `users`, `history` collections
- **Todo** — `lists`, `tasks` collections, `binding_mode: none` (no object binding)
- **Scheduler** — `tasks` collection, cron + Python code validation, enable/disable
