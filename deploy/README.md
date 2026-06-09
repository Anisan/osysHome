# Deploy: nginx + HTTPS + systemd

> **Full documentation:** [docs/DEPLOY_PRODUCTION.md](../docs/DEPLOY_PRODUCTION.md) (EN) · [docs/DEPLOY_PRODUCTION.ru.md](../docs/DEPLOY_PRODUCTION.ru.md) (RU)

Production layout for osysHome when the instance is reachable from the internet or a VPN.

```
Internet / LAN
      │
      ▼
  nginx :443 (TLS)
      │
      ▼
  osysHome 127.0.0.1:5000
```

Do **not** expose port `5000` on the router. Only **443** (and **80** for ACME redirect) should be public.

---

## 1. Application config (`config.yaml`)

After copying `sample_config.yaml`:

1. On first start with the sample `secret_key`, osysHome auto-generates a key and applies safe defaults (comments in the file are kept).
2. For HTTPS behind nginx, set manually (see `deploy/config.production.snippet.yaml`):

```yaml
application:
  session_cookie_secure: true
  session_cookie_samesite: Lax
  debug: false
  env: production
```

Reload osysHome after changing `config.yaml`.

---

## 2. Native install + systemd

### Prepare

```bash
sudo useradd --system --home /opt/osyshome --shell /usr/sbin/nologin osyshome
sudo mkdir -p /opt/osyshome
sudo chown osyshome:osyshome /opt/osyshome

# as root or with sudo -u osyshome
cd /opt/osyshome
git clone https://github.com/Anisan/osysHome.git .
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp sample_config.yaml config.yaml
# edit config.yaml — add your notes; session_cookie_secure after TLS is ready
./scripts/install_recommended_plugins.sh   # Linux
```

### systemd

```bash
sudo cp deploy/systemd/osyshome.service /etc/systemd/system/
# adjust User, WorkingDirectory, ExecStart if not using /opt/osyshome
sudo systemctl daemon-reload
sudo systemctl enable --now osyshome
sudo systemctl status osyshome
```

Logs: `journalctl -u osyshome -f`

### Firewall (example: ufw)

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
# do NOT allow 5000/tcp from outside
sudo ufw enable
```

---

## 3. nginx + Let's Encrypt

### Install nginx and certbot

```bash
sudo apt install nginx certbot python3-certbot-nginx
```

### Site config

```bash
sudo cp deploy/nginx/osyshome.conf /etc/nginx/sites-available/osyshome.conf
sudo sed -i 's/home.example.com/YOUR.DOMAIN/g' /etc/nginx/sites-available/osyshome.conf
sudo ln -sf /etc/nginx/sites-available/osyshome.conf /etc/nginx/sites-enabled/
sudo nginx -t
```

### Certificate (webroot)

```bash
sudo mkdir -p /var/www/certbot
sudo certbot certonly --webroot -w /var/www/certbot -d YOUR.DOMAIN
sudo systemctl reload nginx
```

Or with nginx plugin after the HTTP server block is active:

```bash
sudo certbot --nginx -d YOUR.DOMAIN
```

Renewal is usually handled by `certbot.timer`.

### Enable HTTPS cookie flag

Set `session_cookie_secure: true` in `config.yaml`, then:

```bash
sudo systemctl restart osyshome
```

---

## 4. Docker + nginx on the host

Keep the container on localhost only. In `docker-compose.yml` use:

```yaml
ports:
  - "127.0.0.1:5000:5000"
```

nginx site: `deploy/nginx/osyshome-docker.conf` (same steps as above).

---

## 5. Post-deploy checks

```bash
# TLS and redirect
curl -I https://YOUR.DOMAIN/

# Login page
curl -s https://YOUR.DOMAIN/login | head

# Role / SQL access (optional, against your instance)
python scripts/verify_role_access.py https://YOUR.DOMAIN
```

In the browser (DevTools → Application → Cookies): session cookie must have **Secure** after login.

---

## 6. Security reminders

| Item | Action |
|------|--------|
| `secret_key` | Unique; not the sample value |
| Admin password | Strong; set on first login |
| Guest `user` accounts | Only if you need them; API can control devices |
| `app.db` backups | Encrypted storage; contains api keys (plaintext today) |
| API keys | Prefer header `X-API-Key`, not `?apikey=` in URLs |

---

## Files in this folder

| File | Purpose |
|------|---------|
| `nginx/osyshome.conf` | HTTPS reverse proxy (native or any backend on :5000) |
| `nginx/osyshome-docker.conf` | Same, documented for Docker on 127.0.0.1:5000 |
| `systemd/osyshome.service` | Run `main.py` under dedicated user |
| `config.production.snippet.yaml` | Recommended `config.yaml` keys for HTTPS |
