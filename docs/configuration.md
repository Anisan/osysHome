# System Configuration

All osysHome configuration is stored in the `config.yaml` file at the project root. This file is created from the `sample_config.yaml` template during initial setup.

---

## File Structure

```yaml
application:   # Core application settings
database:      # Database settings
cache:         # Cache settings
service:       # Service management
```

---

## `application` Section

```yaml
application:
  default_language: 'en'
  default_timezone: 'Europe/Moscow'
  secret_key: 'your-secret-key-here'
  debug: false
  app_port: 5000
  env: 'production'
  pool_size: 20
  pool_max_size: 100
  pool_timeout_threshold: 60.0
  batch_writer_flush_interval: 0.5
  session_lifetime_days: 31
  http_request_timeout: 15
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `default_language` | UI language (`ru`, `en`) | `en` |
| `default_timezone` | Timezone for date/time display | `Europe/Moscow` |
| `secret_key` | Flask secret key for session signing. **Must be changed!** | — |
| `debug` | Debug mode: `true` — detailed errors in browser, `false` — production | `false` |
| `app_port` | HTTP server port | `5000` |
| `env` | Environment (`production` / `development`) | `production` |
| `pool_size` | Base thread pool size for method execution | `20` |
| `pool_max_size` | Maximum thread pool size | `100` |
| `pool_timeout_threshold` | Threshold (sec) for warnings about long-running pool tasks | `60.0` |
| `batch_writer_flush_interval` | Interval (sec) for batching property value writes to DB | `0.5` |
| `session_lifetime_days` | User session lifetime in days | `31` |
| `http_request_timeout` | HTTP request timeout (sec) | `15` |

### Rate Limiting

```yaml
application:
  rate_limit:
    enabled: true
    default: '100 per minute'
    login: '5 per minute'
    api: '100 per minute'
```

| Parameter | Description |
|-----------|-------------|
| `enabled` | Enable brute-force / DoS protection |
| `default` | Global rate limit for all routes |
| `login` | Strict limit for the login page |
| `api` | Limit for the REST API |

### Session Security (for HTTPS)

```yaml
application:
  session_cookie_secure: true    # HTTPS only!
  session_cookie_samesite: 'Lax' # CSRF protection
```

> Keep `session_cookie_secure: false` when running without HTTPS (local deployment).

---

## `database` Section

### SQLite (default, requires no installation)

```yaml
database:
  sqlalchemy_echo: false
  pool_size: 5
  db_name: 'app.db'
```

The database is created automatically in the project root on first run.

### PostgreSQL (recommended for production)

```bash
# Install driver
pip install psycopg2-binary
```

```yaml
database:
  sqlalchemy_echo: false
  pool_size: 20
  connection_string: 'postgresql://user:password@localhost/osyshome'
```

### MySQL / MariaDB

```bash
pip install PyMySQL
```

```yaml
database:
  connection_string: 'mysql+pymysql://user:password@localhost/osyshome'
```

| Parameter | Description |
|-----------|-------------|
| `sqlalchemy_echo` | Print SQL queries to log (debug only) |
| `pool_size` | SQLAlchemy connection pool size |
| `db_name` | SQLite filename (ignored if `connection_string` is set) |
| `connection_string` | Connection string for PostgreSQL or MySQL |

---

## `cache` Section

```yaml
cache:
  file_path: 'cache'
  type: 'simple'
  timeout: 300
```

| Parameter | Description |
|-----------|-------------|
| `file_path` | Directory for file cache (TTS MP3 files and other data) |
| `type` | Cache type: `simple` — in-memory, `filesystem` — file-based |
| `timeout` | Cache entry lifetime in seconds |

---

## `service` Section

```yaml
service:
  autorestart: false
  name: null
```

| Parameter | Description |
|-----------|-------------|
| `autorestart` | Allow service restart from the web interface |
| `name` | systemd service name (e.g., `osyshome`) for UI control |

---

## Security Tips

1. **Change `secret_key`** — use a random string of 32+ characters:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Don't commit `config.yaml`** to a public repository — the file contains passwords and secrets.

3. **Enable `session_cookie_secure: true`** when using HTTPS / nginx proxy.

4. **In production** set `debug: false` and `sqlalchemy_echo: false`.

5. **PostgreSQL** is preferred over SQLite for more than 5–10 active users or a high frequency of device state updates.
