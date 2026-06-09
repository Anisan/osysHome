# Аналитика osysHome

Система сбора анонимной аналитики по образцу [Home Assistant Analytics](https://www.home-assistant.io/integrations/analytics/).

## Структура

- **NextGetSmart** — собирает и отправляет данные (с явного согласия пользователя)
- **WordPress (osysHome.ru)** — принимает и сохраняет данные в БД

## Установка endpoint на WordPress

**Важно:** mu-plugins загружают только .php файлы в корне `wp-content/mu-plugins/` (не в подпапках).

1. Создайте папку `wp-content/mu-plugins/` если её нет
2. Скопируйте содержимое `osyshome-analytics-endpoint.php` в новый файл `wp-content/mu-plugins/osyshome-analytics.php`
3. Проверка: откройте `https://osysHome.ru/wp-json/osyshome/v1/analytics` (GET) — должна быть JSON с `"status":"ok"`
4. Endpoint для отправки: `POST https://osysHome.ru/wp-json/osyshome/v1/analytics` с `Content-Type: application/json`

**Если маршрут не работает (404 rest_no_route):**
- Убедитесь, что файл лежит именно в `wp-content/mu-plugins/osyshome-analytics.php`, а не в подпапке
- Или добавьте код в `functions.php` активной темы

**Хранение:** Одна запись на UUID — при повторном запросе от той же установки данные обновляются. Для существующей таблицы без UNIQUE(uuid) выполните:  
`ALTER TABLE wp_osyshome_analytics ADD UNIQUE KEY uuid (uuid);` (и при необходимости удалите дубликаты).

**Статистика:**
- API: `GET https://osyshome.ru/wp-json/osyshome/v1/stats`
- Shortcode `[osyshome_stats]` — список установок, по странам и версиям
- Shortcode `[osyshome_stats_charts]` — Pie-графики + карта мира (Chart.js, ECharts)
- Standalone HTML: `osyshome-stats-charts.html` — страница с графиками и картой (по странам). **Данные по городам** — только в админке: **Инструменты → Статистика osysHome** (сессия администратора)

## Миграция GeoIP для старых записей

После обновления endpoint добавлены поля `country_name`, `city`, `latitude`, `longitude`. Для уже существующих записей их нужно заполнить.

### Через админку WordPress (рекомендуется)

1. Войдите в админку.
2. Перейдите: **Инструменты → GeoIP миграция**.
3. Нажмите кнопку «Запустить миграцию».

### Через REST API

**Вариант A — будучи залогиненным администратором:**
Откройте в той же сессии: `https://ваш-сайт.ru/wp-json/osyshome/v1/migrate-geoip`

**Вариант B — по секретному ключу:**
1. Добавьте в `wp-config.php` (перед «That's all»):
   ```php
   define('OSYSHOME_MIGRATE_KEY', 'ваш-случайный-ключ-минимум-16-символов');
   ```
2. Откройте:
   ```
   https://ваш-сайт.ru/wp-json/osyshome/v1/migrate-geoip?key=ваш-случайный-ключ-минимум-16-символов
   ```

В ответе будет JSON: `updated`, `skipped`, `total`.

### Через консоль

**Вариант 1 (WP-CLI):**
```bash
wp eval-file docs/analytics/osyshome-geoip-migrate.php
```

**Вариант 2 (PHP):**
```bash
php docs/analytics/osyshome-geoip-migrate.php
```

Запускать из корня WordPress. Миграция перебирает все записи. Сервис GeoIP: ipinfo.io. Пауза ~1.4 сек между запросами.

## Собираемые данные

**Basic:** `uuid`, `version`, `os`, `core_branch`, `installation_type`, `country` (по IP)

**Extended:** Basic + `integrations`, `integration_count`, `object_count`, `user_count`, `class_count`, `property_count`, `method_count`, `history_count`

## График отправки

- Первая отправка — через 15 минут после старта
- Далее — ежедневно в 4:00 (cron)

## Opt-in

Пользователь явно выбирает «Да» или «Нет» в панели управления. Пока выбор не сделан, данные не отправляются.
