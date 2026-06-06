# Production-развёртывание (nginx + HTTPS)

Руководство по публикации osysHome в интернете или через VPN с терминацией TLS на **nginx**.  
Готовые конфиги — в [`deploy/`](../deploy/README.md).

---

## Когда использовать этот документ

| Сценарий | Рекомендация |
|----------|--------------|
| Доступ из интернета | nginx + HTTPS + надёжный пароль admin |
| Только домашняя LAN | Достаточно `http://хост:5000` |
| Удалённый доступ без проброса портов | VPN (WireGuard, Tailscale) + LAN-установка |

**Целевая схема:**

```
Клиент (браузер / API)
        │
        ▼
   nginx :443  (TLS, опционально rate limit)
        │
        ▼
   osysHome 127.0.0.1:5000
        │
        └── SQLite app.db, plugins/, files/
```

Порт **5000** на роутере **не пробрасывайте**. Снаружи — только **443** (и **80** для ACME).

---

## Чеклист безопасности

Перед выходом в сеть:

| # | Пункт | Пояснение |
|---|-------|-----------|
| 1 | `secret_key` | Не должен совпадать с образцом в `sample_config.yaml` |
| 2 | `debug: false` | Обязательно в production |
| 3 | `session_cookie_secure: true` | Обязательно при доступе по HTTPS |
| 4 | Пароль admin | Задаётся при первом входе (пустая БД → создание admin) |
| 5 | Firewall | Открыть 80/443; закрыть 5000 снаружи |
| 6 | Гостевые `user` | Только при необходимости; API управляет устройствами |
| 7 | Бэкапы | Храните `app.db` в защищённом месте (apikey пока в plaintext) |

См. также [Безопасность и доступ](SECURITY_ACCESS.ru.md).

### Автонастройка при образцовом secret_key

Если `secret_key` в `config.yaml` совпадает с `sample_config.yaml`, при **первом старте** osysHome:

- генерирует случайный `secret_key`;
- включает безопасные значения (`debug: false`, `env: production`, rate limit, debug tools off);
- обновляет `config.yaml` **на месте** — комментарии сохраняются (точечная правка строк, без доп. зависимостей).

После появления HTTPS вручную включите `session_cookie_secure: true`.

Фрагмент настроек: [`deploy/config.production.snippet.yaml`](../deploy/config.production.snippet.yaml)

---

## `config.yaml` для HTTPS

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

Перезапустите osysHome после изменений.

---

## Вариант A — установка на хост + systemd

### 1. Установка приложения

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

Отредактируйте `config.yaml`; `session_cookie_secure` — после настройки TLS.

### 2. Служба systemd

```bash
sudo cp deploy/systemd/osyshome.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now osyshome
journalctl -u osyshome -f
```

Файл unit: [`deploy/systemd/osyshome.service`](../deploy/systemd/osyshome.service)

### 3. Firewall (пример ufw)

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## Вариант B — Docker + nginx на хосте

Приложение только на localhost:

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.nginx-host.yaml up -d
```

Конфиг nginx: [`deploy/nginx/osyshome-docker.conf`](../deploy/nginx/osyshome-docker.conf)

---

## nginx + Let's Encrypt

```bash
sudo apt install nginx certbot python3-certbot-nginx
sudo cp deploy/nginx/osyshome.conf /etc/nginx/sites-available/osyshome.conf
sudo sed -i 's/home.example.com/ВАШ.ДОМЕН/g' /etc/nginx/sites-available/osyshome.conf
sudo ln -sf /etc/nginx/sites-available/osyshome.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d ВАШ.ДОМЕН
```

### WebSocket (Socket.IO)

В конфиге nginx есть `location /socket.io/` с заголовками `Upgrade` — нужно для плагина **wsServer** (живые обновления UI).

---

## Проверка после деплоя

```bash
curl -I https://ВАШ.ДОМЕН/
python scripts/verify_role_access.py https://ВАШ.ДОМЕН
```

В браузере: cookie сессии после логина должна иметь флаг **Secure**.

Логи: `journalctl -u osyshome -f` или `docker compose logs -f`, аудит — `logs/security_audit.log`.

---

## Типичные проблемы

| Симптом | Причина | Решение |
|---------|---------|---------|
| Цикл логина | `session_cookie_secure: false` при HTTPS | `session_cookie_secure: true`, перезапуск |
| Ошибки CSRF | Нет `X-Forwarded-Proto` | Проверить заголовки proxy в nginx |
| Обрыв WebSocket | Нет прокси `/socket.io/` | Конфиг из `deploy/nginx/` |
| 502 Bad Gateway | Приложение не слушает :5000 | `systemctl status osyshome` |
| Rate limit на login | Много попыток входа | Подождать 15 мин |

---

## Файлы в `deploy/`

| Файл | Назначение |
|------|------------|
| [`deploy/README.md`](../deploy/README.md) | Краткий чеклист |
| [`deploy/nginx/osyshome.conf`](../deploy/nginx/osyshome.conf) | HTTPS reverse proxy |
| [`deploy/systemd/osyshome.service`](../deploy/systemd/osyshome.service) | unit systemd |
| [`deploy/docker-compose.nginx-host.yaml`](../deploy/docker-compose.nginx-host.yaml) | Docker на 127.0.0.1 |

---

## См. также

- [Конфигурация](configuration.ru.md)
- [Безопасность и доступ](SECURITY_ACCESS.ru.md)
- [Быстрый старт (self-host)](QUICKSTART_selfhost.md)
- [Troubleshooting](TROUBLESHOOTING.md)
