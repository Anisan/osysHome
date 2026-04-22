# Boot Sequence

This page documents the real startup order used by `main.py` and `app.createApp(...)`.

## Startup Flow Diagram

```mermaid
flowchart TD
  A[Load Config from config.yaml] --> B[createApp(Config)]
  B --> C[Register blueprints/extensions]
  C --> D[sync_db core tables]
  D --> E[registerPlugins app]
  E --> F[sync_db plugin tables]
  F --> G[initSystemVar]
  G --> H[start_plugins]
  H --> I[init_analytics_scheduler]
  I --> J[app.run threaded]
```

## Runtime Order

1. `Config` is loaded from `config.yaml` (`app/configuration.py`).
2. `app = createApp(Config)` is executed.
3. Inside `createApp`:
   - Flask app is created and extensions are configured.
   - Core blueprints are registered (`api`, `auth`, `admin`, `files`).
   - `sync_db(app)` is called (core tables).
   - `registerPlugins(app)` discovers and instantiates active plugins.
   - `sync_db(app)` is called again (plugin tables).
   - Intelli cache is built.
4. In `main.py` before `app.run(...)`:
   - `initSystemVar()` inside app context.
   - `start_plugins()` (calls plugin `initialization()`, then starts `cycle` threads).
   - `startSystemVar()`.
   - `init_analytics_scheduler()` inside app context.
5. Flask server starts with `threaded=True`.

## Why Two `sync_db(...)` Calls

- First pass ensures core schema exists.
- After plugin import/registration, plugin models become visible.
- Second pass synchronizes plugin-related tables.

## Related Docs

- [Architecture](ARCHITECTURE.md)
- [Core Runtime](CORE_RUNTIME.md)
- [Security & Access](SECURITY_ACCESS.md)
- [Consistency & Timezones](CONSISTENCY_TIMEZONES.md)

## Key References

- `main.py`
- `app/__init__.py` (`createApp`)
- `app/core/main/PluginsHelper.py`
- `app/database.py` (`sync_db`)
