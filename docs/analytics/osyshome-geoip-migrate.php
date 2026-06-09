<?php
/**
 * Миграция: заполнение GeoIP (country_name, city, lat, lon) для существующих записей.
 *
 * Запуск:
 *   wp eval-file docs/analytics/osyshome-geoip-migrate.php
 *
 * Или из корня WordPress:
 *   php -r "require 'wp-load.php'; require 'docs/analytics/osyshome-geoip-migrate.php';"
 *
 * Сервис: ipinfo.io. Между запросами — пауза ~1.4 сек.
 */

if (!defined('ABSPATH')) {
    $wp_load = dirname(__DIR__) . '/wp-load.php';
    if (!is_file($wp_load)) {
        $wp_load = dirname(__DIR__, 2) . '/wp-load.php';
    }
    require_once $wp_load;
}

global $wpdb;
$table = $wpdb->prefix . 'osyshome_analytics';

$col = $wpdb->get_results("SHOW COLUMNS FROM {$table} LIKE 'city'");
if (empty($col)) {
    die("Колонки geo не найдены. Сначала обновите endpoint.\n");
}

$rows = $wpdb->get_results("SELECT id, payload FROM {$table}", ARRAY_A);

$code_to_name = ['RU' => 'Russia', 'US' => 'United States', 'DE' => 'Germany', 'GB' => 'United Kingdom', 'FR' => 'France', 'UA' => 'Ukraine', 'BY' => 'Belarus', 'KZ' => 'Kazakhstan', 'CN' => 'China', 'JP' => 'Japan'];

function osyshome_geoip_migrate_lookup($ip, $code_to_name) {
    if (empty($ip) || in_array($ip, ['127.0.0.1', '::1'])) {
        return null;
    }
    $url = 'https://ipinfo.io/' . urlencode($ip) . '/json';
    $r = wp_remote_get($url, ['timeout' => 5]);
    if (is_wp_error($r) || wp_remote_retrieve_response_code($r) !== 200) {
        return null;
    }
    $d = json_decode(wp_remote_retrieve_body($r), true);
    if (!is_array($d) || empty($d['loc'])) {
        return null;
    }
    $loc = explode(',', $d['loc']);
    $lat = isset($loc[0]) && is_numeric(trim($loc[0])) ? (float) trim($loc[0]) : null;
    $lon = isset($loc[1]) && is_numeric(trim($loc[1])) ? (float) trim($loc[1]) : null;
    $code = $d['country'] ?? '';
    return [
        'country_code' => $code,
        'country_name' => $code_to_name[$code] ?? $code,
        'city'         => $d['city'] ?? '',
        'lat'          => $lat,
        'lon'          => $lon,
    ];
}

$updated = 0;
$skipped = 0;

foreach ($rows as $row) {
    $p = json_decode($row['payload'] ?? '{}', true);
    $ip = $p['client_ip'] ?? '';
    if (empty($ip)) {
        $skipped++;
        continue;
    }

    $geo = osyshome_geoip_migrate_lookup($ip, $code_to_name);
    if (!$geo) {
        $skipped++;
        continue;
    }

    $wpdb->update(
        $table,
        [
            'country'      => $geo['country_code'],
            'country_name' => $geo['country_name'],
            'city'         => $geo['city'],
            'latitude'     => $geo['lat'],
            'longitude'    => $geo['lon'],
        ],
        ['id' => $row['id']],
        ['%s', '%s', '%s', '%f', '%f'],
        ['%d']
    );

    if ($wpdb->rows_affected) {
        $updated++;
    }

    usleep(1400000); // ~1.4 сек — укладываемся в 45 запросов/мин
}

echo "Готово. Обновлено: {$updated}, пропущено: {$skipped}, всего проверено: " . count($rows) . "\n";
