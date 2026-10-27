# Disk write optimization (Raspberry Pi / microSD)

Reduce microSD wear when running osysHome on Raspberry Pi-class hardware. This covers **core** `config.yaml` knobs only; per-plugin tuning is out of scope here.

**Full guide (strategies soft → hard, copy-paste Pi profile, PG/MySQL server tips):** [DISK_WRITE_OPTIMIZATION.ru.md](DISK_WRITE_OPTIMIZATION.ru.md)

Also see [configuration.md](configuration.md) and comments in `sample_config.yaml`.

## What writes to disk

1. Rotating log files (`logging.*`)
2. `BatchWriter` commits for property values / history (`application.batch_writer_*`)
3. SQLite WAL / fsync (`database.sqlite.*`)

## Strategy cheat sheet

| Strategy | Intent | Typical knobs | Main risks |
|----------|--------|---------------|------------|
| **Soft** | Less log noise, slightly fewer commits | `min_level: WARNING`, `per_module_files: false`, flush `2.0`, `synchronous: NORMAL` | Low |
| **Medium** (recommended Pi start) | Clearly fewer SD writes | flush `5.0`, memory log buffer, `temp_store: MEMORY`, logs on tmpfs; limit `history` on chatty sensors | RAM logs lost on reboot; delayed value persistence |
| **Hard** | Minimal SD writes | `file_enabled: false`, flush `10+`, `synchronous: OFF`, DB on USB, `history: 0` on chatty sensors | Data loss on power cut; weak file diagnostics |

## Minimal medium profile (YAML)

```yaml
application:
  debug: false
  batch_writer_flush_interval: 5.0
  batch_writer_max_size: 200

logging:
  min_level: WARNING
  file_enabled: true
  console_enabled: true
  directory: logs
  per_module_files: false
  memory_handler_capacity: 50
  backup_count: 3

database:
  db_name: 'app.db'
  sqlite:
    journal_mode: WAL
    synchronous: NORMAL
    temp_store: MEMORY
    cache_size: -65536
```

History always keeps every change point — limit chatty sensors via property `history` days / `0`. Prefer `cache.type: simple`. Keep PostgreSQL/MySQL data directories off microSD; use server settings such as `synchronous_commit=off` / `innodb_flush_log_at_trx_commit=2` only if you accept durability trade-offs.

**Stop/restart:** `app/graceful_shutdown.py` flushes `BatchWriter` on SIGTERM/SIGINT and before WebSocket `restart_system` (`os._exit`). See the RU guide for the full table. Power loss / SIGKILL still loses the current flush window.
