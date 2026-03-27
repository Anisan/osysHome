# System Configuration

All osysHome configuration is stored in the `config.yaml` file at the project root. This file is created from the `sample_config.yaml` template during initial setup.

## File Structure

```yaml
application:   # Core application settings
database:      # Database settings
debug_tools:   # Optional heavy debug tools
cache:         # Cache settings
service:       # Service management
```

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
  session_cookie_secure: false
  session_cookie_samesite: 'Lax'
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `default_language` | Default UI language (`en`, `ru`, `de`, etc.) | `en` |
| `default_timezone` | Default timezone for displaying dates and times | `Europe/Moscow` |
| `secret_key` | Flask secret key used for sessions and tokens. Must be changed in real deployments. | `your-secret-key-here` |
| `debug` | Global application debug mode | `false` |
| `app_port` | HTTP port used by the application | `5000` |
| `env` | Environment name such as `production` or `development` | `production` |
| `pool_size` | Base size of the internal worker thread pool | `20` |
| `pool_max_size` | Maximum size of the worker thread pool | `100` |
| `pool_timeout_threshold` | Threshold in seconds after which a pool task is considered slow | `60.0` |
| `batch_writer_flush_interval` | Forced flush interval for batched writes in seconds | `0.5` |
| `session_lifetime_days` | User session lifetime in days | `31` |
| `http_request_timeout` | Default timeout for outbound HTTP requests in seconds | `15` |
| `session_cookie_secure` | Require HTTPS for the session cookie | `false` |
| `session_cookie_samesite` | SameSite policy for the session cookie | `Lax` |

### Rate Limiting

```yaml
application:
  rate_limit:
    enabled: true
    default: '100 per minute'
    login: '5 per minute'
    api: '100 per minute'
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `enabled` | Enable brute-force / overload protection | `true` |
| `default` | Default limit for all routes | `100 per minute` |
| `login` | Dedicated limit for the login page | `5 per minute` |
| `api` | Limit for API routes | `100 per minute` |

## `database` Section

### SQLite Example

```yaml
database:
  sqlalchemy_echo: false
  pool_size: 20
  db_name: 'app.db'
```

The SQLite database file is created automatically in the project root on first run.

### PostgreSQL Example

```yaml
database:
  sqlalchemy_echo: false
  pool_size: 20
  connection_string: 'postgresql://user:password@localhost/osyshome'
```

### MySQL / MariaDB Example

```yaml
database:
  sqlalchemy_echo: false
  pool_size: 20
  connection_string: 'mysql+pymysql://user:password@localhost/osyshome'
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `sqlalchemy_echo` | Print SQL statements to the log | `false` |
| `pool_size` | SQLAlchemy connection pool size | `20` |
| `db_name` | SQLite filename, used when `connection_string` is not set | `app.db` |
| `connection_string` | External database connection string for PostgreSQL/MySQL/MariaDB | not set |

## `debug_tools` Section

This section controls optional heavy debugging features. It is separate from `application.debug`, so you can keep normal Flask debug mode enabled while leaving expensive tooling disabled.

```yaml
debug_tools:
  enabled: false
  template_editor_enabled: false
  profiler_enabled: false
  profiler_dump_filename: 'dump.prof'
  intercept_redirects: false
  sqlalchemy_record_queries: false
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `enabled` | Enable Flask Debug Toolbar | `false` |
| `template_editor_enabled` | Enable the template editor inside Debug Toolbar | `false` |
| `profiler_enabled` | Enable request profiling in Debug Toolbar | `false` |
| `profiler_dump_filename` | Output filename used by the profiler | `dump.prof` |
| `intercept_redirects` | Intercept redirects in Debug Toolbar instead of following them normally | `false` |
| `sqlalchemy_record_queries` | Collect SQL query statistics for each HTTP request | `false` |

## `cache` Section

```yaml
cache:
  file_path: 'cache'
  type: 'simple'
  timeout: 300
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `file_path` | Path to the cache directory | `cache` |
| `type` | Cache backend type, for example `simple` | `simple` |
| `timeout` | Cache entry lifetime in seconds | `300` |

## `service` Section

```yaml
service:
  autorestart: false
  name: null
  docker_container: null
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `autorestart` | Allow built-in restart actions to restart the service automatically | `false` |
| `name` | systemd service name used for restart/control operations | `null` |
| `docker_container` | Docker container name used for restart/control operations | `null` |

## Security Tips

1. Change `secret_key` to a long random value before production use.
2. Do not commit `config.yaml` to a public repository.
3. Set `session_cookie_secure: true` when running behind HTTPS.
4. In production, keep `debug: false`, `sqlalchemy_echo: false`, and `debug_tools.enabled: false`.
5. Enable `sqlalchemy_record_queries` only temporarily while investigating slow pages.
