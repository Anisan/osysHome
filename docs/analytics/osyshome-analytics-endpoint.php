<?php
/**
 * osysHome Analytics Receiver - WordPress Endpoint
 *
 * Устанавлика:
 * 1. Создайте папку wp-content/mu-plugins/ если её нет
 * 2. Скопируйте этот файл как wp-content/mu-plugins/osyshome-analytics.php
 * 3. Либо добавьте код в functions.php темы
 *
 * Endpoint: POST https://osysHome.ru/?rest_route=/osyshome/v1/analytics
 * Content-Type: application/json
 *
 * При необходимости добавьте правила rewrite в .htaccess для /api/osyshome/v1/analytics
 * или используйте стандартный REST API: ?rest_route=/osyshome/v1/analytics
 */

add_action('admin_menu', function () {
    add_management_page(
        'Миграция GeoIP osysHome',
        'GeoIP миграция',
        'manage_options',
        'osyshome-migrate-geoip',
        'osyshome_admin_migrate_geoip_page'
    );
    add_management_page(
        'Статистика osysHome',
        'Статистика osysHome',
        'manage_options',
        'osyshome-stats-charts',
        'osyshome_admin_stats_charts_page'
    );
    add_management_page(
        'Установки osysHome',
        'Установки osysHome',
        'manage_options',
        'osyshome-installations',
        'osyshome_admin_installations_page'
    );
});

function osyshome_admin_stats_charts_page() {
    if (!current_user_can('manage_options')) {
        wp_die(__('Access denied'));
    }
    echo '<div class="wrap"><p><a href="' . esc_url(admin_url('tools.php')) . '">← Инструменты</a> | <a href="' . esc_url(admin_url('tools.php?page=osyshome-installations')) . '">Установки</a></p>';
    echo osyshome_stats_charts_shortcode();
    echo '</div>';
}

function osyshome_admin_migrate_geoip_page() {
    if (!current_user_can('manage_options')) {
        wp_die(__('Access denied'));
    }
    $result = null;
    if (isset($_GET['run']) && isset($_GET['_wpnonce']) && wp_verify_nonce($_GET['_wpnonce'], 'osyshome_migrate_geoip')) {
        $response = osyshome_analytics_migrate_geoip();
        $result = $response->get_data();
    }
    ?>
    <div class="wrap">
        <h1>Миграция GeoIP для osysHome</h1>
        <p>Обновляет GeoIP (country, country_name, city, latitude, longitude) для всех записей. Сервис: ipinfo.io</p>
        <?php if ($result !== null): ?>
            <div class="notice notice-<?php echo isset($result['error']) ? 'error' : 'success'; ?> is-dismissible">
                <p><?php
                    if (isset($result['error'])) {
                        echo esc_html($result['error']);
                    } else {
                        echo 'Обновлено: ' . (int)($result['updated'] ?? 0) . ', пропущено: ' . (int)($result['skipped'] ?? 0) . ', всего: ' . (int)($result['total'] ?? 0);
                    }
                ?></p>
            </div>
        <?php endif; ?>
        <p>
            <a href="<?php echo esc_url(wp_nonce_url(admin_url('tools.php?page=osyshome-migrate-geoip&run=1'), 'osyshome_migrate_geoip', '_wpnonce')); ?>" class="button button-primary">Запустить миграцию</a>
        </p>
    </div>
    <?php
}

function osyshome_admin_installations_page() {
    if (!current_user_can('manage_options')) {
        wp_die(__('Access denied'));
    }
    $api_url = rest_url('osyshome/v1/admin/installations');
    $rest_nonce = wp_create_nonce('wp_rest');
    ?>
    <div class="wrap">
        <h1>Установки osysHome</h1>
        <p><a href="<?php echo esc_url(admin_url('tools.php?page=osyshome-stats-charts')); ?>">← Статистика</a></p>

        <div id="osh-summary" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem;margin:1.5rem 0;"></div>

        <div style="background:#fff;padding:1.25rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08);margin:1.5rem 0;">
            <h2 style="font-size:1rem;margin:0 0 1rem;color:#333;">Активность установок по дням</h2>
            <canvas id="osh-activity-chart" height="80"></canvas>
        </div>

        <div style="margin:1.5rem 0;display:flex;gap:1rem;align-items:center;flex-wrap:wrap;">
            <input type="text" id="osh-search" placeholder="Поиск по UUID, стране, городу, версии…"
                   style="width:300px;padding:6px 12px;border:1px solid #8c8f94;border-radius:4px;">
            <select id="osh-filter" style="padding:6px 12px;border:1px solid #8c8f94;border-radius:4px;">
                <option value="all">Все</option>
                <option value="active">Активные (7 дней)</option>
                <option value="recent">Недавние (30 дней)</option>
                <option value="stale">Неактивные (30+ дней)</option>
            </select>
            <span id="osh-count" style="color:#666;font-size:0.9rem;"></span>
        </div>

        <div style="background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08);overflow-x:auto;">
            <table class="wp-list-table widefat striped" id="osh-table">
                <thead>
                    <tr>
                        <th data-sort="index" style="cursor:pointer;width:40px;">#</th>
                        <th data-sort="uuid" style="cursor:pointer;">UUID</th>
                        <th data-sort="location" style="cursor:pointer;">Расположение</th>
                        <th data-sort="version" style="cursor:pointer;">Версия</th>
                        <th data-sort="os" style="cursor:pointer;">ОС</th>
                        <th data-sort="branch" style="cursor:pointer;">Ветка</th>
                        <th data-sort="type" style="cursor:pointer;">Тип</th>
                        <th data-sort="objects" style="cursor:pointer;text-align:center;">Объекты</th>
                        <th data-sort="updated" style="cursor:pointer;">Обновлено</th>
                    </tr>
                </thead>
                <tbody id="osh-tbody">
                    <tr><td colspan="9" style="text-align:center;padding:2rem;">Загрузка…</td></tr>
                </tbody>
            </table>
        </div>
        <p id="osh-error" style="display:none;color:#c00;margin-top:1rem;"></p>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <script>
    (function(){
        var allData=[],sortCol='updated',sortDir=-1;

        function flag(code){
            if(!code||code.length!==2)return '';
            var c=code.toUpperCase();
            return String.fromCodePoint(0x1F1E6+c.charCodeAt(0)-65,0x1F1E6+c.charCodeAt(1)-65)+' ';
        }

        function daysSince(ds){return Math.floor((Date.now()-new Date(ds.replace(' ','T')))/864e5);}

        function timeAgo(ds){
            var d=Math.floor((Date.now()-new Date(ds.replace(' ','T')))/1000);
            if(d<60)return 'только что';
            if(d<3600)return Math.floor(d/60)+' мин назад';
            if(d<86400)return Math.floor(d/3600)+' ч назад';
            var days=Math.floor(d/86400);
            if(days<2)return 'вчера';
            if(days<7)return days+' дн назад';
            if(days<30)return Math.floor(days/7)+' нед назад';
            if(days<365)return Math.floor(days/30)+' мес назад';
            return Math.floor(days/365)+' г назад';
        }

        function stClass(ds){var d=daysSince(ds);return d<=7?'active':d<=30?'recent':'stale';}

        function badge(ds){
            var d=daysSince(ds);
            if(d<=7)return '<span style="display:inline-block;background:#4CAF50;color:#fff;padding:2px 8px;border-radius:12px;font-size:.75rem;margin-right:4px">Активна</span>';
            if(d<=30)return '<span style="display:inline-block;background:#FF9800;color:#fff;padding:2px 8px;border-radius:12px;font-size:.75rem;margin-right:4px">Недавно</span>';
            return '<span style="display:inline-block;background:#9E9E9E;color:#fff;padding:2px 8px;border-radius:12px;font-size:.75rem;margin-right:4px">Неактивна</span>';
        }

        function renderSummary(data){
            var t=data.total||0,a7=0,r30=0,st=0;
            (data.installations||[]).forEach(function(x){
                var d=daysSince(x.received_at);
                if(d<=7)a7++;else if(d<=30)r30++;else st++;
            });
            var cards=[
                {l:'Всего установок',v:t,c:'#4CAF50,#45a049'},
                {l:'Активных (7\u00a0дн)',v:a7,c:'#2196F3,#1976D2'},
                {l:'Недавних (30\u00a0дн)',v:r30,c:'#FF9800,#F57C00'},
                {l:'Неактивных',v:st,c:'#9E9E9E,#757575'}
            ];
            document.getElementById('osh-summary').innerHTML=cards.map(function(c){
                var cs=c.c.split(',');
                return '<div style="background:linear-gradient(135deg,'+cs[0]+','+cs[1]+');color:#fff;padding:1rem;border-radius:8px;text-align:center">'
                    +'<div style="font-size:1.75rem;font-weight:700;font-variant-numeric:tabular-nums">'+c.v+'</div>'
                    +'<div style="font-size:.85rem;opacity:.9">'+c.l+'</div></div>';
            }).join('');
        }

        function renderChart(act){
            var labels=Object.keys(act),vals=labels.map(function(k){return act[k];});
            if(!labels.length)return;
            new Chart(document.getElementById('osh-activity-chart'),{
                type:'bar',
                data:{labels:labels,datasets:[{label:'Установок обновилось',data:vals,backgroundColor:'rgba(33,150,243,.7)',borderColor:'#1976D2',borderWidth:1,borderRadius:3}]},
                options:{responsive:true,maintainAspectRatio:true,plugins:{legend:{display:false},tooltip:{callbacks:{label:function(i){return i.raw+' установок';}}}},scales:{x:{ticks:{maxRotation:45,font:{size:10}},grid:{display:false}},y:{beginAtZero:true,ticks:{stepSize:1}}}}
            });
        }

        function esc(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML;}

        function renderTable(list){
            var tb=document.getElementById('osh-tbody');
            if(!list.length){tb.innerHTML='<tr><td colspan="9" style="text-align:center;padding:2rem;color:#666">Нет данных</td></tr>';return;}
            tb.innerHTML=list.map(function(x,i){
                var loc='';
                if(x.city||x.country_name||x.country)loc=flag(x.country)+[x.city,x.country_name||x.country].filter(Boolean).join(', ');
                var dt=x.received_at.replace(' ','T');
                var fmtDate='';
                try{var dd=new Date(dt);fmtDate=dd.toLocaleDateString('ru-RU')+' '+dd.toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'});}catch(e){fmtDate=x.received_at;}
                return '<tr>'
                    +'<td>'+(i+1)+'</td>'
                    +'<td title="'+esc(x.uuid)+'"><code style="font-size:.8rem">'+esc(x.uuid.substring(0,12))+'…</code></td>'
                    +'<td>'+(loc?esc(loc):'—')+'</td>'
                    +'<td><code>'+(x.version?esc(x.version):'—')+'</code></td>'
                    +'<td>'+(x.os?esc(x.os):'—')+'</td>'
                    +'<td>'+(x.core_branch?esc(x.core_branch):'—')+'</td>'
                    +'<td>'+(x.installation_type?esc(x.installation_type):'—')+'</td>'
                    +'<td style="text-align:center">'+x.object_count+'</td>'
                    +'<td style="white-space:nowrap">'+badge(x.received_at)+'<span title="'+esc(fmtDate)+'" style="font-size:.85rem;color:#666">'+esc(timeAgo(x.received_at))+'</span></td>'
                    +'</tr>';
            }).join('');
        }

        function applyFilters(){
            var q=document.getElementById('osh-search').value.toLowerCase();
            var st=document.getElementById('osh-filter').value;
            var f=allData.filter(function(x){
                if(st!=='all'&&stClass(x.received_at)!==st)return false;
                if(q){var h=[x.uuid,x.country,x.country_name,x.city,x.version,x.os,x.core_branch,x.installation_type].join(' ').toLowerCase();if(h.indexOf(q)===-1)return false;}
                return true;
            });
            f.sort(function(a,b){
                var va,vb;
                switch(sortCol){
                    case 'uuid':va=a.uuid;vb=b.uuid;break;
                    case 'location':va=(a.city||'')+(a.country||'');vb=(b.city||'')+(b.country||'');break;
                    case 'version':va=a.version;vb=b.version;break;
                    case 'os':va=a.os;vb=b.os;break;
                    case 'branch':va=a.core_branch;vb=b.core_branch;break;
                    case 'type':va=a.installation_type;vb=b.installation_type;break;
                    case 'objects':va=a.object_count;vb=b.object_count;break;
                    default:va=a.received_at;vb=b.received_at;
                }
                return va<vb?-sortDir:va>vb?sortDir:0;
            });
            renderTable(f);
            document.getElementById('osh-count').textContent='Показано: '+f.length+' из '+allData.length;
        }

        document.getElementById('osh-search').addEventListener('input',applyFilters);
        document.getElementById('osh-filter').addEventListener('change',applyFilters);

        document.querySelectorAll('#osh-table th[data-sort]').forEach(function(th){
            th.addEventListener('click',function(){
                var c=this.getAttribute('data-sort');
                if(sortCol===c)sortDir*=-1;else{sortCol=c;sortDir=c==='updated'?-1:1;}
                document.querySelectorAll('#osh-table th[data-sort]').forEach(function(h){h.textContent=h.textContent.replace(/ [▲▼]$/,'');h.style.color='';});
                this.style.color='#2196F3';this.textContent+=sortDir>0?' ▲':' ▼';
                applyFilters();
            });
        });

        fetch(<?php echo wp_json_encode($api_url); ?>,{credentials:'include',headers:{'X-WP-Nonce':<?php echo wp_json_encode($rest_nonce); ?>}})
            .then(function(r){return r.json();})
            .then(function(data){
                allData=data.installations||[];
                renderSummary(data);
                renderChart(data.activity||{});
                applyFilters();
            })
            .catch(function(e){var el=document.getElementById('osh-error');el.textContent='Ошибка загрузки: '+e.message;el.style.display='block';});
    })();
    </script>
    <?php
}

function osyshome_admin_installations_api() {
    global $wpdb;
    $table = $wpdb->prefix . 'osyshome_analytics';
    if ($wpdb->get_var("SHOW TABLES LIKE '{$table}'") != $table) {
        return new WP_REST_Response(['installations' => [], 'activity' => [], 'total' => 0], 200);
    }
    $rows = $wpdb->get_results(
        "SELECT uuid, payload, country, country_name, city, version, received_at FROM {$table} ORDER BY received_at DESC",
        ARRAY_A
    );
    $installations = [];
    $activity = [];
    foreach ($rows as $row) {
        $p = json_decode($row['payload'] ?? '{}', true);
        if (!is_array($p)) $p = [];
        $date = substr($row['received_at'], 0, 10);
        $activity[$date] = ($activity[$date] ?? 0) + 1;
        $installations[] = [
            'uuid'              => $row['uuid'],
            'country'           => $row['country'],
            'country_name'      => $row['country_name'],
            'city'              => $row['city'],
            'version'           => $row['version'],
            'os'                => $p['os'] ?? '',
            'core_branch'       => $p['core_branch'] ?? '',
            'installation_type' => $p['installation_type'] ?? '',
            'object_count'      => (int) ($p['object_count'] ?? 0),
            'user_count'        => (int) ($p['user_count'] ?? 0),
            'integration_count' => (int) ($p['integration_count'] ?? 0),
            'received_at'       => $row['received_at'],
        ];
    }
    ksort($activity);
    return new WP_REST_Response([
        'installations' => $installations,
        'activity'      => $activity,
        'total'         => count($installations),
    ], 200);
}

add_action('rest_api_init', function () {
    register_rest_route('osyshome/v1', '/stats', [
        'methods'             => 'GET',
        'callback'            => 'osyshome_analytics_stats',
        'permission_callback' => '__return_true',
    ]);
    register_rest_route('osyshome/v1', '/migrate-geoip', [
        'methods'             => 'GET',
        'callback'            => 'osyshome_analytics_migrate_geoip',
        'permission_callback' => function (WP_REST_Request $req) {
            if (current_user_can('manage_options')) {
                return true;
            }
            $key = $req->get_param('key');
            if ($key && defined('OSYSHOME_MIGRATE_KEY') && hash_equals((string) OSYSHOME_MIGRATE_KEY, (string) $key)) {
                return true;
            }
            return false;
        },
    ]);
    register_rest_route('osyshome/v1', '/admin/installations', [
        'methods'             => 'GET',
        'callback'            => 'osyshome_admin_installations_api',
        'permission_callback' => function () {
            return current_user_can('manage_options');
        },
    ]);
    register_rest_route('osyshome/v1', '/analytics', [
        [
            'methods'             => 'GET',
            'callback'            => function () {
                return new WP_REST_Response(['status' => 'ok', 'message' => 'Send POST with JSON body to receive analytics'], 200);
            },
            'permission_callback' => '__return_true',
        ],
        [
            'methods'             => 'POST',
            'callback'            => 'osyshome_analytics_receive',
            'permission_callback' => '__return_true',
            'args'                => [
                'uuid' => [
                    'required'          => true,
                    'type'              => 'string',
                    'sanitize_callback' => 'sanitize_text_field',
                ],
            ],
        ],
    ]);
});

function osyshome_analytics_receive(WP_REST_Request $request) {
    $body = $request->get_json_params();
    if (!$body || !is_array($body)) {
        return new WP_REST_Response(['error' => 'Invalid JSON'], 400);
    }

    $uuid = isset($body['uuid']) ? sanitize_text_field($body['uuid']) : '';
    if (empty($uuid) || strlen($uuid) < 10) {
        return new WP_REST_Response(['error' => 'Invalid uuid'], 400);
    }

    global $wpdb;
    $table_name = $wpdb->prefix . 'osyshome_analytics';

    // Создаём таблицу при первом запросе
    if ($wpdb->get_var("SHOW TABLES LIKE '{$table_name}'") != $table_name) {
        osyshome_analytics_create_table($wpdb, $table_name);
    }

    // GeoIP по IP
    $ip = $_SERVER['REMOTE_ADDR'] ?? '';
    if (!empty($_SERVER['HTTP_X_FORWARDED_FOR'])) {
        $ips = explode(',', $_SERVER['HTTP_X_FORWARDED_FOR']);
        $ip = trim($ips[0]);
    }
    $geo = osyshome_analytics_geoip($ip);

    $payload = [
        'uuid'               => $uuid,
        'version'            => isset($body['version']) ? sanitize_text_field($body['version']) : '',
        'os'                 => isset($body['os']) ? sanitize_text_field($body['os']) : '',
        'core_branch'        => isset($body['core_branch']) ? sanitize_text_field($body['core_branch']) : '',
        'installation_type'  => isset($body['installation_type']) ? sanitize_text_field($body['installation_type']) : '',
        'country'            => $geo['country_code'],
        'country_name'       => $geo['country_name'],
        'city'               => $geo['city'],
        'lat'                => $geo['lat'],
        'lon'                => $geo['lon'],
        'integrations'       => isset($body['integrations']) && is_array($body['integrations'])
            ? array_map('sanitize_text_field', $body['integrations']) : [],
        'integration_count'  => isset($body['integration_count']) ? absint($body['integration_count']) : 0,
        'object_count'       => isset($body['object_count']) ? absint($body['object_count']) : 0,
        'user_count'         => isset($body['user_count']) ? absint($body['user_count']) : 0,
        'class_count'        => isset($body['class_count']) ? absint($body['class_count']) : 0,
        'property_count'     => isset($body['property_count']) ? absint($body['property_count']) : 0,
        'method_count'       => isset($body['method_count']) ? absint($body['method_count']) : 0,
        'history_count'      => isset($body['history_count']) ? absint($body['history_count']) : 0,
        'received_at'        => current_time('mysql'),
        'client_ip'          => $ip,
    ];

    // Дополнительные поля (опционально)
    if (isset($body['recorder_engine'])) {
        $payload['recorder_engine'] = sanitize_text_field($body['recorder_engine']);
    }
    if (isset($body['certificate'])) {
        $payload['certificate'] = (bool) $body['certificate'];
    }

    $json_payload = wp_json_encode($payload);

    $row = [
        'uuid'         => $uuid,
        'payload'      => $json_payload,
        'country'      => $geo['country_code'],
        'country_name' => $geo['country_name'],
        'city'         => $geo['city'],
        'latitude'     => $geo['lat'] !== null ? $geo['lat'] : null,
        'longitude'    => $geo['lon'] !== null ? $geo['lon'] : null,
        'version'      => $payload['version'],
        'received_at'  => $payload['received_at'],
    ];
    $formats = ['%s', '%s', '%s', '%s', '%s', '%f', '%f', '%s', '%s'];

    // Одна запись на UUID: обновляем при повторном запросе
    $exists = $wpdb->get_var($wpdb->prepare(
        "SELECT id FROM {$table_name} WHERE uuid = %s",
        $uuid
    ));
    if ($exists) {
        $result = $wpdb->update(
            $table_name,
            $row,
            ['uuid' => $uuid],
            $formats,
            ['%s']
        );
    } else {
        $result = $wpdb->insert($table_name, $row, $formats);
    }

    if ($result === false) {
        return new WP_REST_Response(['error' => 'Database error'], 500);
    }

    if (defined('WP_DEBUG') && WP_DEBUG) {
        error_log('[osysHome Analytics] ' . ($exists ? 'Updated' : 'Inserted') . ' uuid=' . $uuid);
    }

    return new WP_REST_Response(['ok' => true, 'updated' => (bool) $exists], 200);
}

function osyshome_analytics_stats() {
    global $wpdb;
    $table = $wpdb->prefix . 'osyshome_analytics';
    if ($wpdb->get_var("SHOW TABLES LIKE '{$table}'") != $table) {
        return new WP_REST_Response(osyshome_analytics_empty_stats(), 200);
    }
    $total = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$table}");
    $geo_cols_exists = $wpdb->get_results("SHOW COLUMNS FROM {$table} LIKE 'country_name'");
    $country_name_col = !empty($geo_cols_exists);
    $by_country = $country_name_col
        ? $wpdb->get_results("SELECT country, MAX(NULLIF(TRIM(country_name),'')) as country_name, COUNT(*) as cnt FROM {$table} WHERE country != '' GROUP BY country ORDER BY cnt DESC", ARRAY_A)
        : $wpdb->get_results("SELECT country, COUNT(*) as cnt FROM {$table} WHERE country != '' GROUP BY country ORDER BY cnt DESC", ARRAY_A);
    $by_version = $wpdb->get_results("SELECT version, COUNT(*) as cnt FROM {$table} WHERE version != '' GROUP BY version ORDER BY cnt DESC", ARRAY_A);
    $by_city = [];
    if ($country_name_col) {
        $by_city = $wpdb->get_results(
            "SELECT city, country, country_name, AVG(latitude) as lat, AVG(longitude) as lon, COUNT(*) as cnt 
             FROM {$table} 
             WHERE city != '' AND country != '' AND latitude IS NOT NULL AND longitude IS NOT NULL 
             GROUP BY city, country, country_name 
             ORDER BY cnt DESC",
            ARRAY_A
        );
    }
    $rows = $wpdb->get_results("SELECT payload FROM {$table}", ARRAY_A);

    $countries = [];
    $map_countries = [];
    $code_to_name = [
        'RU' => 'Russia', 'US' => 'United States', 'DE' => 'Germany', 'GB' => 'United Kingdom', 'FR' => 'France',
        'UA' => 'Ukraine', 'BY' => 'Belarus', 'KZ' => 'Kazakhstan', 'CN' => 'China', 'JP' => 'Japan',
        'IN' => 'India', 'BR' => 'Brazil', 'IT' => 'Italy', 'ES' => 'Spain', 'PL' => 'Poland',
        'NL' => 'Netherlands', 'BE' => 'Belgium', 'CZ' => 'Czech Republic', 'AT' => 'Austria', 'CH' => 'Switzerland',
        'TR' => 'Turkey', 'IL' => 'Israel', 'CA' => 'Canada', 'AU' => 'Australia', 'KR' => 'South Korea',
    ];
    foreach ($by_country as $r) {
        $code = $r['country'];
        $cnt = (int) $r['cnt'];
        $countries[$code] = $cnt;
        // Для карты используем стабильное имя по ISO-коду, а не country_name из GeoIP.
        $name = $code_to_name[$code] ?? $code;
        $map_countries[] = ['name' => $name, 'value' => $cnt];
    }
    $versions = [];
    foreach ($by_version as $r) {
        $versions[$r['version']] = (int) $r['cnt'];
    }

    $by_integration = [];
    $by_installation_type = [];
    $by_os = [];
    $by_core_branch = [];
    $sum_objects = 0;
    $sum_users = 0;
    $sum_classes = 0;
    $sum_properties = 0;
    $sum_methods = 0;
    $sum_history = 0;

    foreach ($rows as $row) {
        $p = json_decode($row['payload'] ?? '{}', true);
        if (!is_array($p)) continue;
        foreach ($p['integrations'] ?? [] as $mod) {
            $name = preg_replace('/@.*/', '', (string) $mod);
            if ($name !== '') {
                $by_integration[$name] = ($by_integration[$name] ?? 0) + 1;
            }
        }
        $it = $p['installation_type'] ?? '';
        if ($it !== '') {
            $by_installation_type[$it] = ($by_installation_type[$it] ?? 0) + 1;
        }
        $os = $p['os'] ?? '';
        if ($os !== '') {
            $by_os[$os] = ($by_os[$os] ?? 0) + 1;
        }
        $branch = $p['core_branch'] ?? '';
        if ($branch !== '') {
            $by_core_branch[$branch] = ($by_core_branch[$branch] ?? 0) + 1;
        }
        $sum_objects += (int) ($p['object_count'] ?? 0);
        $sum_users += (int) ($p['user_count'] ?? 0);
        $sum_classes += (int) ($p['class_count'] ?? 0);
        $sum_properties += (int) ($p['property_count'] ?? 0);
        $sum_methods += (int) ($p['method_count'] ?? 0);
        $sum_history += (int) ($p['history_count'] ?? 0);
    }
    arsort($by_integration);
    arsort($by_installation_type);
    arsort($by_os);
    arsort($by_core_branch);

    $cities_for_map = [];
    if (current_user_can('manage_options')) {
        foreach ($by_city as $r) {
            $cities_for_map[] = [
                'city'         => $r['city'],
                'country'      => $r['country'],
                'country_name' => $r['country_name'] ?? '',
                'lat'          => (float) $r['lat'],
                'lon'          => (float) $r['lon'],
                'count'        => (int) $r['cnt'],
            ];
        }
    }

    return new WP_REST_Response([
        'installations'        => $total,
        'total_objects'        => $sum_objects,
        'total_users'          => $sum_users,
        'total_classes'        => $sum_classes,
        'total_properties'     => $sum_properties,
        'total_methods'        => $sum_methods,
        'total_history'        => $sum_history,
        'by_country'           => $countries,
        'map_countries'        => $map_countries,
        'by_city'              => $cities_for_map,
        'by_version'           => $versions,
        'by_integration'       => $by_integration,
        'by_installation_type' => $by_installation_type,
        'by_os'                => $by_os,
        'by_core_branch'       => $by_core_branch,
    ], 200);
}

function osyshome_analytics_migrate_geoip() {
    set_time_limit(600);
    global $wpdb;
    $table = $wpdb->prefix . 'osyshome_analytics';
    if ($wpdb->get_var("SHOW TABLES LIKE '{$table}'") != $table) {
        return new WP_REST_Response(['error' => 'Таблица аналитики не найдена'], 400);
    }
    osyshome_analytics_maybe_add_geo_columns($wpdb, $table);
    $col = $wpdb->get_results("SHOW COLUMNS FROM {$table} LIKE 'city'");
    if (empty($col)) {
        return new WP_REST_Response(['error' => 'Не удалось добавить колонки geo'], 400);
    }
    $rows = $wpdb->get_results("SELECT id, payload FROM {$table}", ARRAY_A);
    $updated = 0;
    $skipped = 0;
    foreach ($rows as $row) {
        $p = json_decode($row['payload'] ?? '{}', true);
        $ip = $p['client_ip'] ?? '';
        if (empty($ip)) {
            $skipped++;
            continue;
        }
        $geo = osyshome_analytics_geoip($ip);
        if (empty($geo['country_code']) && empty($geo['city'])) {
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
        usleep(1400000);
    }
    return new WP_REST_Response([
        'ok'       => true,
        'updated'  => $updated,
        'skipped'  => $skipped,
        'total'    => count($rows),
        'message'  => "Обновлено: {$updated}, пропущено: {$skipped}, всего: " . count($rows),
    ], 200);
}

function osyshome_analytics_empty_stats() {
    return [
        'installations'        => 0,
        'total_objects'        => 0,
        'total_users'          => 0,
        'total_classes'        => 0,
        'total_properties'     => 0,
        'total_methods'        => 0,
        'total_history'        => 0,
        'by_country'           => [],
        'map_countries'        => [],
        'by_city'              => [],
        'by_version'           => [],
        'by_integration'       => [],
        'by_installation_type' => [],
        'by_os'                => [],
        'by_core_branch'       => [],
    ];
}

function osyshome_analytics_create_table($wpdb, $table_name) {
    $charset = $wpdb->get_charset_collate();
    $sql = "CREATE TABLE {$table_name} (
        id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
        uuid varchar(64) NOT NULL,
        payload longtext NOT NULL,
        country varchar(4) DEFAULT '',
        country_name varchar(64) DEFAULT '',
        city varchar(128) DEFAULT '',
        latitude decimal(10,7) DEFAULT NULL,
        longitude decimal(11,7) DEFAULT NULL,
        version varchar(32) DEFAULT '',
        received_at datetime NOT NULL,
        PRIMARY KEY (id),
        UNIQUE KEY uuid (uuid),
        KEY received_at (received_at),
        KEY country (country),
        KEY city (city(32))
    ) $charset;";
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    dbDelta($sql);
    osyshome_analytics_maybe_add_geo_columns($wpdb, $table_name);
}

function osyshome_analytics_maybe_add_geo_columns($wpdb, $table_name) {
    $col = $wpdb->get_results("SHOW COLUMNS FROM {$table_name} LIKE 'city'");
    if (empty($col)) {
        $wpdb->query("ALTER TABLE {$table_name} ADD COLUMN country_name varchar(64) DEFAULT '' AFTER country");
        $wpdb->query("ALTER TABLE {$table_name} ADD COLUMN city varchar(128) DEFAULT '' AFTER country_name");
        $wpdb->query("ALTER TABLE {$table_name} ADD COLUMN latitude decimal(10,7) DEFAULT NULL AFTER city");
        $wpdb->query("ALTER TABLE {$table_name} ADD COLUMN longitude decimal(11,7) DEFAULT NULL AFTER latitude");
    }
}

/**
 * GeoIP по IP: страна, город, координаты.
 * Использует ipinfo.io (бесплатно, до 50k запросов/мес без ключа).
 */
function osyshome_analytics_geoip($ip) {
    $empty = ['country_code' => '', 'country_name' => '', 'city' => '', 'lat' => null, 'lon' => null];
    if (empty($ip) || $ip === '127.0.0.1' || $ip === '::1') {
        return $empty;
    }
    $code_to_name = [
        'RU' => 'Russia', 'US' => 'United States', 'DE' => 'Germany', 'GB' => 'United Kingdom', 'FR' => 'France',
        'UA' => 'Ukraine', 'BY' => 'Belarus', 'KZ' => 'Kazakhstan', 'CN' => 'China', 'JP' => 'Japan',
    ];
    $url = 'https://ipinfo.io/' . urlencode($ip) . '/json';
    $response = wp_remote_get($url, ['timeout' => 5]);
    if (is_wp_error($response) || wp_remote_retrieve_response_code($response) !== 200) {
        return $empty;
    }
    $data = json_decode(wp_remote_retrieve_body($response), true);
    if (!is_array($data) || empty($data['loc'])) {
        return $empty;
    }
    $loc = explode(',', $data['loc']);
    $lat = isset($loc[0]) && is_numeric(trim($loc[0])) ? (float) trim($loc[0]) : null;
    $lon = isset($loc[1]) && is_numeric(trim($loc[1])) ? (float) trim($loc[1]) : null;
    $code = isset($data['country']) ? sanitize_text_field($data['country']) : '';
    return [
        'country_code' => $code,
        'country_name' => $code_to_name[$code] ?? $code,
        'city'         => isset($data['city']) ? sanitize_text_field($data['city']) : '',
        'lat'          => $lat,
        'lon'          => $lon,
    ];
}

// Shortcode для вывода статистики: [osyshome_stats]
add_shortcode('osyshome_stats', 'osyshome_stats_shortcode');

// Shortcode с Pie-графиками: [osyshome_stats_charts]
add_shortcode('osyshome_stats_charts', 'osyshome_stats_charts_shortcode');

function osyshome_stats_charts_shortcode() {
    $api_url = rest_url('osyshome/v1/stats');
    $rest_nonce = wp_create_nonce('wp_rest');
    ob_start();
    ?>
    <div class="osyshome-stats-charts" style="font-family:system-ui,sans-serif;max-width:1200px;margin:0 auto;">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
        <style>
            .osyshome-kpi-value{font-size:clamp(1.15rem,2.2vw,1.75rem)!important;font-weight:700;line-height:1.1;white-space:nowrap;font-variant-numeric:tabular-nums}
        </style>
        <div class="osyshome-kpi" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin:1.5rem 0;">
            <div style="background:linear-gradient(135deg,#4CAF50,#45a049);color:#fff;padding:1rem;border-radius:8px;text-align:center;">
                <div class="osyshome-kpi-value" style="font-size:1.75rem;font-weight:700;" id="osyshome-total">—</div>
                <div style="font-size:0.85rem;opacity:0.9;">Установок</div>
            </div>
            <div style="background:linear-gradient(135deg,#2196F3,#1976D2);color:#fff;padding:1rem;border-radius:8px;text-align:center;">
                <div class="osyshome-kpi-value" style="font-size:1.75rem;font-weight:700;" id="osyshome-objects">—</div>
                <div style="font-size:0.85rem;opacity:0.9;">Объектов</div>
            </div>
            <div style="background:linear-gradient(135deg,#FF9800,#F57C00);color:#fff;padding:1rem;border-radius:8px;text-align:center;">
                <div class="osyshome-kpi-value" style="font-size:1.75rem;font-weight:700;" id="osyshome-users">—</div>
                <div style="font-size:0.85rem;opacity:0.9;">Пользователей</div>
            </div>
            <div style="background:linear-gradient(135deg,#009688,#00796B);color:#fff;padding:1rem;border-radius:8px;text-align:center;">
                <div class="osyshome-kpi-value" style="font-size:1.75rem;font-weight:700;" id="osyshome-classes">—</div>
                <div style="font-size:0.85rem;opacity:0.9;">Классов</div>
            </div>
            <div style="background:linear-gradient(135deg,#673AB7,#512DA8);color:#fff;padding:1rem;border-radius:8px;text-align:center;">
                <div class="osyshome-kpi-value" style="font-size:1.75rem;font-weight:700;" id="osyshome-properties">—</div>
                <div style="font-size:0.85rem;opacity:0.9;">Свойств</div>
            </div>
            <div style="background:linear-gradient(135deg,#3F51B5,#303F9F);color:#fff;padding:1rem;border-radius:8px;text-align:center;">
                <div class="osyshome-kpi-value" style="font-size:1.75rem;font-weight:700;" id="osyshome-methods">—</div>
                <div style="font-size:0.85rem;opacity:0.9;">Методов</div>
            </div>
            <div style="background:linear-gradient(135deg,#795548,#5D4037);color:#fff;padding:1rem;border-radius:8px;text-align:center;">
                <div class="osyshome-kpi-value" style="font-size:1.75rem;font-weight:700;" id="osyshome-history">—</div>
                <div style="font-size:0.85rem;opacity:0.9;">История</div>
            </div>
        </div>
        <div style="background:#fff;padding:1.25rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08);margin:2rem 0;">
            <h2 style="font-size:1rem;margin:0 0 1rem;color:#333;">География установок</h2>
            <div id="osyshome-map-container" style="width:100%;height:450px;background:#f5f5f5;border-radius:8px;"></div>
        </div>
        <div class="osyshome-charts" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.5rem;margin:2rem 0;">
            <div style="background:#fff;padding:1.25rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08);">
                <h2 style="font-size:1rem;margin:0 0 1rem;color:#333;">По странам</h2>
                <canvas id="osyshome-chart-country" height="220"></canvas>
            </div>
            <div style="background:#fff;padding:1.25rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08);">
                <h2 style="font-size:1rem;margin:0 0 1rem;color:#333;">По версиям</h2>
                <canvas id="osyshome-chart-version" height="220"></canvas>
            </div>
            <div style="background:#fff;padding:1.25rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08);">
                <h2 style="font-size:1rem;margin:0 0 1rem;color:#333;">По модулям (Топ-20)</h2>
                <canvas id="osyshome-chart-integration" height="440"></canvas>
            </div>
            <div style="background:#fff;padding:1.25rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08);">
                <h2 style="font-size:1rem;margin:0 0 1rem;color:#333;">Тип установки</h2>
                <canvas id="osyshome-chart-installation" height="220"></canvas>
            </div>
            <div style="background:#fff;padding:1.25rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08);">
                <h2 style="font-size:1rem;margin:0 0 1rem;color:#333;">ОС</h2>
                <canvas id="osyshome-chart-os" height="220"></canvas>
            </div>
            <div style="background:#fff;padding:1.25rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08);">
                <h2 style="font-size:1rem;margin:0 0 1rem;color:#333;">Ветка обновлений</h2>
                <canvas id="osyshome-chart-branch" height="220"></canvas>
            </div>
        </div>
        <p id="osyshome-error" style="display:none;color:#c00;"></p>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <script>
    (function(){
        var colors = ['#4CAF50','#2196F3','#FF9800','#9C27B0','#F44336','#00BCD4','#795548','#607D8B','#E91E63','#3F51B5'];
        function makePie(id,labels,values){
            var ctx = document.getElementById(id);
            if(!ctx || !labels.length) return;
            new Chart(ctx,{type:'pie',data:{labels:labels,datasets:[{data:values,backgroundColor:colors,borderWidth:1}]},options:{responsive:true,maintainAspectRatio:true,plugins:{legend:{position:'right',labels:{boxWidth:12,font:{size:11}}}}}});
        }
        function makeBar(id,labels,values,barOptions){
            var ctx = document.getElementById(id);
            if(!ctx || !labels.length) return;
            var opts = {indexAxis:'y',responsive:true,maintainAspectRatio:true,plugins:{legend:{display:false}},layout:{padding:{left:2,right:10}},scales:{x:{beginAtZero:true,ticks:{stepSize:1}},y:{ticks:{autoSkip:false,font:{size:10},maxRotation:0}}}};
            if (barOptions) {
                for (var k in barOptions) { opts[k] = barOptions[k]; }
            }
            new Chart(ctx,{type:'bar',data:{labels:labels,datasets:[{data:values,backgroundColor:colors[0],borderRadius:4}]},options:opts});
        }
        function osyshomeInitMap(data){
            var c=document.getElementById('osyshome-map-container');
            if(!c||(!(data.map_countries||[]).length&&!(data.by_city||[]).length))return;
            var chart=echarts.init(c);
            var mapUrl='https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@master/geojson/ne_110m_admin_0_countries.geojson';
            fetch(mapUrl).then(function(r){return r.json();})
            .then(function(geo){
                (geo.features||[]).forEach(function(f){if(f.properties){var n=f.properties.NAME||f.properties.name||'';var alias={'Russian Federation':'Russia','The Netherlands':'Netherlands','United States of America':'United States','United Kingdom':'United Kingdom'}[n]||n;f.properties.name=alias;}});
                echarts.registerMap('world',geo);
                var mapData=data.map_countries||[], cities=(data.by_city||[]).map(function(x){return{name:x.city+(x.country_name?', '+x.country_name:''),value:[x.lon,x.lat,x.count]};});
                var series=[];
                if(mapData.length) series.push({type:'map',map:'world',geoIndex:0,roam:true,data:mapData,emphasis:{label:{show:true},itemStyle:{areaColor:'#ffd700'}},itemStyle:{areaColor:'#e0e0e0',borderColor:'#90a4ae'}});
                if(cities.length) series.push({type:'effectScatter',coordinateSystem:'geo',data:cities,symbolSize:function(v){return Math.max(8,Math.min(30,Math.sqrt(v[2])*4));},showEffectOn:'render',rippleEffect:{scale:2.5,brushType:'stroke'},label:{show:false},itemStyle:{color:'#f44336',shadowBlur:10,shadowColor:'rgba(244,67,54,0.5)'}});
                var maxVal=mapData.length?Math.max.apply(null,mapData.map(function(d){return d.value;})):1;
                chart.setOption({tooltip:{trigger:'item',formatter:function(p){if(p.seriesType==='map'){return p.name+': '+(p.value||0)+' установок';} if(p.value&&p.value[2]!=null){return p.name+': '+p.value[2]+' установок';} return p.name;}},visualMap:mapData.length?{min:0,max:Math.max(maxVal,1),text:['Много','Мало'],inRange:{color:['#e3f2fd','#1976d2','#0d47a1']},left:'left',bottom:20}:null,geo:{map:'world',roam:true,silent:false,itemStyle:{areaColor:'#e0e0e0',borderColor:'#90a4ae'}},series:series});
            }).catch(function(){});
        }
        fetch(<?php echo wp_json_encode($api_url); ?>, { credentials: 'include', headers: { 'X-WP-Nonce': <?php echo wp_json_encode($rest_nonce); ?> } })
            .then(function(r){return r.json();})
            .then(function(data){
                osyshomeInitMap(data);
                document.getElementById('osyshome-total').textContent = data.installations || 0;
                document.getElementById('osyshome-objects').textContent = (data.total_objects||0).toLocaleString();
                document.getElementById('osyshome-users').textContent = (data.total_users||0).toLocaleString();
                document.getElementById('osyshome-classes').textContent = (data.total_classes||0).toLocaleString();
                document.getElementById('osyshome-properties').textContent = (data.total_properties||0).toLocaleString();
                document.getElementById('osyshome-methods').textContent = (data.total_methods||0).toLocaleString();
                document.getElementById('osyshome-history').textContent = (data.total_history||0).toLocaleString();
                var c=Object.keys(data.by_country||{}), cv=c.map(function(k){return data.by_country[k];});
                var v=Object.keys(data.by_version||{}), vv=v.map(function(k){return data.by_version[k];});
                var i=Object.keys(data.by_integration||{}), iv=i.map(function(k){return data.by_integration[k];});
                var t=Object.keys(data.by_installation_type||{}), tv=t.map(function(k){return data.by_installation_type[k];});
                var o=Object.keys(data.by_os||{}), ov=o.map(function(k){return data.by_os[k];});
                var b=Object.keys(data.by_core_branch||{}), bv=b.map(function(k){return data.by_core_branch[k];});
                makePie('osyshome-chart-country',c,cv);
                makePie('osyshome-chart-version',v,vv);
                makeBar('osyshome-chart-integration',i.slice(0,20),iv.slice(0,20));
                makePie('osyshome-chart-installation',t,tv);
                makePie('osyshome-chart-os',o,ov);
                makePie('osyshome-chart-branch',b,bv);
            })
            .catch(function(err){document.getElementById('osyshome-error').textContent='Ошибка загрузки: '+err.message;document.getElementById('osyshome-error').style.display='block';});
    })();
    </script>
    <?php
    return ob_get_clean();
}

function osyshome_stats_shortcode() {
    $url = rest_url('osyshome/v1/stats');
    $response = wp_remote_get($url, ['timeout' => 5]);
    if (is_wp_error($response)) {
        return '<p>Ошибка загрузки статистики.</p>';
    }
    $data = json_decode(wp_remote_retrieve_body($response), true);
    if (!$data) {
        return '<p>Нет данных.</p>';
    }
    $total = (int) ($data['installations'] ?? 0);
    $by_country = $data['by_country'] ?? [];
    $by_version = $data['by_version'] ?? [];
    $by_integration = $data['by_integration'] ?? [];
    $by_installation = $data['by_installation_type'] ?? [];
    ob_start();
    ?>
    <div class="osyshome-stats">
        <h2>Статистика osysHome</h2>
        <p><strong>Установок:</strong> <?php echo esc_html($total); ?>
        | <strong>Объектов:</strong> <?php echo esc_html(number_format_i18n($data['total_objects'] ?? 0)); ?>
        | <strong>Пользователей:</strong> <?php echo esc_html(number_format_i18n($data['total_users'] ?? 0)); ?></p>
        <?php if (!empty($by_country)) : ?><h3>По странам</h3><ul><?php foreach ($by_country as $c => $n) : ?><li><?php echo esc_html($c); ?>: <?php echo (int) $n; ?></li><?php endforeach; ?></ul><?php endif; ?>
        <?php if (!empty($by_version)) : ?><h3>По версиям</h3><ul><?php foreach ($by_version as $v => $n) : ?><li><?php echo esc_html($v); ?>: <?php echo (int) $n; ?></li><?php endforeach; ?></ul><?php endif; ?>
        <?php if (!empty($by_integration)) : ?><h3>По модулям</h3><ul><?php foreach ($by_integration as $m => $n) : ?><li><?php echo esc_html($m); ?>: <?php echo (int) $n; ?></li><?php endforeach; ?></ul><?php endif; ?>
        <?php if (!empty($by_installation)) : ?><h3>Тип установки</h3><ul><?php foreach ($by_installation as $t => $n) : ?><li><?php echo esc_html($t); ?>: <?php echo (int) $n; ?></li><?php endforeach; ?></ul><?php endif; ?>
        <?php if (!empty($data['by_os'] ?? [])) : ?><h3>ОС</h3><ul><?php foreach ($data['by_os'] as $o => $n) : ?><li><?php echo esc_html($o); ?>: <?php echo (int) $n; ?></li><?php endforeach; ?></ul><?php endif; ?>
        <?php if (!empty($data['by_core_branch'] ?? [])) : ?><h3>Ветка обновлений</h3><ul><?php foreach ($data['by_core_branch'] as $br => $n) : ?><li><?php echo esc_html($br); ?>: <?php echo (int) $n; ?></li><?php endforeach; ?></ul><?php endif; ?>
        <?php if ($total === 0) : ?><p><em>Пока нет данных.</em></p><?php endif; ?>
    </div>
    <?php
    return ob_get_clean();
}
