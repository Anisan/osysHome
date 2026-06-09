# Production Deployment (nginx + HTTPS)

Guide for exposing osysHome on the internet or over VPN with TLS termination at **nginx**.  
Ready-made configs live in [`deploy/`](../deploy/README.md).

---

## When to use this guide

| Scenario | Recommendation |
|----------|----------------|
| Access from the internet | nginx + HTTPS + strong admin password |
| Home LAN only | Direct `http://host:5000` is enough |
| Remote access without public exposure | VPN (WireGuard, Tailscale) + LAN setup |

**Target layout:**

```
Client (browser / API)
        │
        ▼
   nginx :443  (TLS, optional rate limits)
        │
        ▼
   osysHome 127.0.0.1:5000
        │
        └── SQLite app.db, plugins/, files/
```

Do **not** port-forward **5000** on your router. Only **443** (and **80** for ACME) should be reachable from outside.

---

## Security checklist

Complete **before** opening the instance to the network:

| # | Item | Notes |
|---|------|-------|
| 1 | `secret_key` | Must not be the sample value from `sample_config.yaml` |
| 2 | `debug: false` | Required in production |
| 3 | `session_cookie_secure: true` | Required when users connect via HTTPS |
| 4 | Admin password | Set on first login (empty DB creates admin) |
| 5 | Firewall | Allow 80/443; block external access to 5000 |
| 6 | Guest `user` accounts | Only if needed; API can control devices |
| 7 | Backups | Protect `app.db` (API keys stored in plaintext today) |

See also [Security & Access](SECURITY_ACCESS.md).

### Automatic config hardening

If `secret_key` in `config.yaml` still matches `sample_config.yaml`, osysHome on **first start**:

- generates a random `secret_key`;
- applies safe defaults (`debug: false`, `env: production`, rate limits, debug tools off);
- updates `config.yaml` **in place** — your YAML comments are preserved (line-based patch, no extra dependencies).

After that, set `session_cookie_secure: true` manually once HTTPS is working.

Snippet: [`deploy/config.production.snippet.yaml`](../deploy/config.production.snippet.yaml)

---

## `config.yaml` for HTTPS

```yaml
application:
  debug: false
  env: production
  app_port: 5000
  session_cookie_secure: true
  session_cookie_samesite: Lax

  rate_limit:
    enabled: true
    login: '5 per minute'
```

Restart osysHome after changes.

---

## Option A — Native install + systemd

### 1. Install application

```bash
sudo useradd --system --home /opt/osyshome --shell /usr/sbin/nologin osyshome
sudo mkdir -p /opt/osyshome
sudo chown osyshome:osyshome /opt/osyshome

cd /opt/osyshome
git clone https://github.com/Anisan/osysHome.git .
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp sample_config.yaml config.yaml
./scripts/install_recommended_plugins.sh
```

Edit `config.yaml` (add your notes; enable `session_cookie_secure` after TLS).

### 2. systemd service

```bash
sudo cp deploy/systemd/osyshome.service /etc/systemd/system/
# Adjust WorkingDirectory / ExecStart if not using /opt/osyshome
sudo systemctl daemon-reload
sudo systemctl enable --now osyshome
journalctl -u osyshome -f
```

Unit file: [`deploy/systemd/osyshome.service`](../deploy/systemd/osyshome.service)

### 3. Firewall (ufw example)

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## Option B — Docker + nginx on host

Keep the app bound to localhost only:

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.nginx-host.yaml up -d
```

Or in `docker-compose.yml`:

```yaml
ports:
  - "127.0.0.1:5000:5000"
```

Use nginx site: [`deploy/nginx/osyshome-docker.conf`](../deploy/nginx/osyshome-docker.conf)

---

## nginx + Let's Encrypt

### Install

```bash
sudo apt install nginx certbot python3-certbot-nginx
```

### Enable site

```bash
sudo cp deploy/nginx/osyshome.conf /etc/nginx/sites-available/osyshome.conf
sudo sed -i 's/home.example.com/YOUR.DOMAIN/g' /etc/nginx/sites-available/osyshome.conf
sudo ln -sf /etc/nginx/sites-available/osyshome.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Certificate

```bash
sudo certbot --nginx -d YOUR.DOMAIN
```

Renewal: `certbot.timer` (systemd).

### WebSocket (Socket.IO)

The nginx config includes a `/socket.io/` location with `Upgrade` headers — required for the **wsServer** plugin (live UI updates, notifications).

---

## Post-deploy verification

```bash
# HTTPS redirect
curl -I https://YOUR.DOMAIN/

# Login page reachable
curl -s https://YOUR.DOMAIN/login | head -20

# Role / SQL access (optional)
python scripts/verify_role_access.py https://YOUR.DOMAIN
```

**Browser:** DevTools → Application → Cookies — session cookie must have **Secure** after login.

**Logs:**

- Native: `journalctl -u osyshome -f`
- Docker: `docker compose logs -f`
- Security audit: `logs/security_audit.log`

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Login loop / session lost | `session_cookie_secure: false` over HTTPS | Set `session_cookie_secure: true`, restart app |
| CSRF errors behind proxy | Missing `X-Forwarded-Proto` | Check nginx `proxy_set_header X-Forwarded-Proto $scheme` |
| WebSocket disconnects | No `/socket.io/` proxy block | Use provided nginx config |
| 502 Bad Gateway | osysHome not running on :5000 | `systemctl status osyshome` or `docker compose ps` |
| Rate limit on login | Too many attempts | Wait 15 min or check `logs/security_audit.log` |

---

## Deploy file reference

| File | Purpose |
|------|---------|
| [`deploy/README.md`](../deploy/README.md) | Short deploy checklist |
| [`deploy/nginx/osyshome.conf`](../deploy/nginx/osyshome.conf) | HTTPS reverse proxy |
| [`deploy/nginx/osyshome-docker.conf`](../deploy/nginx/osyshome-docker.conf) | Same for Docker backend |
| [`deploy/systemd/osyshome.service`](../deploy/systemd/osyshome.service) | systemd unit |
| [`deploy/config.production.snippet.yaml`](../deploy/config.production.snippet.yaml) | `config.yaml` fragment |
| [`deploy/docker-compose.nginx-host.yaml`](../deploy/docker-compose.nginx-host.yaml) | Bind Docker to 127.0.0.1 |

---

## Related documentation

- [Configuration](configuration.md) — all `config.yaml` options
- [Security & Access](SECURITY_ACCESS.md) — auth model, roles, API keys
- [Quickstart (self-host)](QUICKSTART_selfhost.md) — first install and Docker basics
- [Troubleshooting](TROUBLESHOOTING.md) — general issues
