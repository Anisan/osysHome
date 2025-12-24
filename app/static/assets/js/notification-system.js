/**
 * Централизованная система управления уведомлениями
 * Обеспечивает стабильную работу с защитой от race conditions
 */

(function() {
    'use strict';

    // Проверка зависимостей
    if (typeof $ === 'undefined') {
        console.error('NotificationSystem: jQuery is required');
        return;
    }

    const NotificationSystem = {
        // Флаги состояния
        isInitialized: false,
        isRefreshing: false,
        isUpdatingIndicators: false,
        
        // Очереди для предотвращения race conditions
        refreshQueue: [],
        indicatorUpdateQueue: [],
        
        // Таймеры для debouncing
        refreshTimer: null,
        indicatorTimer: null,
        
        // Константы
        REFRESH_DEBOUNCE: 500,
        INDICATOR_DEBOUNCE: 300,
        MAX_RETRIES: 3,
        RETRY_DELAY: 200,
        
        /**
         * Инициализация системы
         */
        init: function() {
            if (this.isInitialized) {
                return;
            }
            
            this.isInitialized = true;
        },
        
        /**
         * Получение текущего source из URL
         */
        getCurrentSource: function() {
            const pathParts = window.location.pathname.split('/').filter(function(p) { return p; });
            const source = pathParts[pathParts.length - 1];
            
            // Проверяем, что это не admin или пустая строка
            if (!source || source === 'admin' || source === '') {
                return null;
            }
            
            return source;
        },
        
        /**
         * Проверка, находимся ли мы на странице модуля
         */
        isOnModulePage: function(source) {
            if (!source) {
                return false;
            }
            
            const currentPath = window.location.pathname;
            const pathParts = currentPath.split('/').filter(function(p) { return p; });
            const currentSource = pathParts[pathParts.length - 1];
            
            return source && (
                currentSource === source || 
                currentPath.includes('/admin/' + source) ||
                currentPath.endsWith('/' + source) ||
                currentPath.endsWith('/admin/' + source)
            );
        },
        
        /**
         * Экранирование HTML для безопасности
         */
        escapeHtml: function(text) {
            if (!text) return '';
            const map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            };
            return String(text).replace(/[&<>"']/g, function(m) { return map[m]; });
        },
        
        /**
         * Поиск элемента уведомления по ID (унифицированный метод)
         */
        findNotifyElement: function(id) {
            if (!id) return $();
            
            // Пробуем несколько способов поиска
            let element = $('.alert[data-notify-id="' + id + '"]');
            
            if (element.length === 0) {
                element = $('button[onclick*="readNotify(' + id + ')"]').closest('.alert');
            }
            
            return element;
        },
        
        /**
         * Обновление счетчика уведомлений в блоке
         */
        updateNotifyBlockCounter: function(count) {
            const notifyBlock = $('#notify_block');
            if (notifyBlock.length === 0) return;
            
            const countElement = notifyBlock.find('.px-3.me-auto');
            const notifyText = notifyBlock.find('.px-3.me-auto').text().split(' - ')[0] || 'Уведомления';
            
            if (countElement.length) {
                countElement.html(notifyText + ' - ' + count);
            } else {
                notifyBlock.find('h5 .px-3.me-auto').html(notifyText + ' - ' + count);
            }
        },
        
        /**
         * Удаление уведомления из DOM
         */
        removeNotifyFromDOM: function(id, callback) {
            const element = this.findNotifyElement(id);
            
            if (element.length) {
                element.fadeOut(300, function() {
                    $(this).remove();
                    if (typeof callback === 'function') {
                        callback();
                    }
                });
            } else {
                if (typeof callback === 'function') {
                    callback();
                }
            }
        },
        
        /**
         * Проверка и скрытие блока уведомлений, если он пуст
         */
        checkAndHideNotifyBlock: function() {
            const notifyBlock = $('#notify_block');
            if (notifyBlock.length === 0) return;
            
            const remainingAlerts = notifyBlock.find('.alert');
            if (remainingAlerts.length === 0) {
                notifyBlock.fadeOut(300, function() {
                    $(this).remove();
                });
            } else {
                this.updateNotifyBlockCounter(remainingAlerts.length);
            }
        },
        
        /**
         * Создание HTML для уведомления
         */
        createNotifyHTML: function(notif) {
            const categoryColors = {
                'Info': 'success',
                'Warning': 'warning',
                'Error': 'danger',
                'Debug': 'secondary',
                'Fatal': 'danger'
            };
            
            const categoryIcons = {
                'Debug': 'fas fa-info-circle',
                'Info': 'fas fa-info-circle',
                'Warning': 'fas fa-exclamation-triangle',
                'Error': 'fas fa-times-circle',
                'Fatal': 'fas fa-stop-circle'
            };
            
            const color = categoryColors[notif.category] || 'danger';
            const icon = categoryIcons[notif.category] || 'fas fa-info-circle';
            const countBadge = notif.count > 1 ? 
                `<span class="badge bg-danger rounded-pill me-2" title="${notif.count} counts">${notif.count}</span>` : '';
            const createdDate = notif.created ? new Date(notif.created).toLocaleString() : '';
            const lastUpdatedDate = notif.last_updated ? new Date(notif.last_updated).toLocaleString() : '';
            let dateInfo = `<i class="fas fa-calendar-plus me-1" title="Created"></i>${createdDate}`;
            if (lastUpdatedDate && notif.count && notif.count > 1) {
                dateInfo += ` <i class="fas fa-clock me-1" title="Last updated"></i>${lastUpdatedDate}`;
            }
            
            const descriptionHtml = notif.description ? 
                `<span class="ms-1">${this.escapeHtml(notif.description)}</span>` : '';
            
            return `
                <div class="alert alert-${color} alert-dismissible fade show p-2 my-1" data-notify-id="${notif.id}">
                    ${countBadge}
                    <i class="${icon} me-1"></i>
                    <b>${this.escapeHtml(notif.name)}</b>
                    ${descriptionHtml}
                    <span class="ms-2">${dateInfo}</span>
                    <button type="button" class="btn-close p-2 my-1" onclick="if(typeof NotificationSystem !== 'undefined') NotificationSystem.readNotify(${notif.id})" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
        },
        
        /**
         * Обновление блока уведомлений (с debouncing и защитой от race conditions)
         */
        refreshNotifyBlock: function(source, force) {
            if (!source) {
                source = this.getCurrentSource();
            }
            
            if (!source) {
                return;
            }
            
            // Если уже идет обновление и это не принудительное, добавляем в очередь
            if (this.isRefreshing && !force) {
                this.refreshQueue.push(source);
                return;
            }
            
            // Очищаем предыдущий таймер
            if (this.refreshTimer) {
                clearTimeout(this.refreshTimer);
            }
            
            // Debouncing
            this.refreshTimer = setTimeout(() => {
                this._doRefreshNotifyBlock(source);
            }, this.REFRESH_DEBOUNCE);
        },
        
        /**
         * Внутренний метод обновления блока уведомлений
         */
        _doRefreshNotifyBlock: function(source) {
            if (this.isRefreshing) {
                return;
            }
            
            this.isRefreshing = true;
            
            $.ajax({
                url: '/api/utils/notifications',
                method: 'GET',
                data: {
                    source: source,
                    unread_only: true
                },
                timeout: 10000,
                success: (data) => {
                    this.isRefreshing = false;
                    
                    if (data && data.success && data.notifications) {
                        this._renderNotifyBlock(source, data.notifications);
                    } else {
                        // Если уведомлений нет, скрываем блок
                        const notifyBlock = $('#notify_block');
                        if (notifyBlock.length) {
                            notifyBlock.fadeOut(300);
                        }
                    }
                    
                    // Обрабатываем очередь
                    this._processRefreshQueue();
                },
                error: (xhr, status, error) => {
                    this.isRefreshing = false;
                    console.error('NotificationSystem: Error refreshing notify block:', error, xhr);
                    
                    // Обрабатываем очередь даже при ошибке
                    this._processRefreshQueue();
                }
            });
        },
        
        /**
         * Обработка очереди обновлений
         */
        _processRefreshQueue: function() {
            if (this.refreshQueue.length > 0) {
                const nextSource = this.refreshQueue.shift();
                setTimeout(() => {
                    this.refreshNotifyBlock(nextSource, true);
                }, this.REFRESH_DEBOUNCE);
            }
        },
        
        /**
         * Рендеринг блока уведомлений
         */
        _renderNotifyBlock: function(source, notifications) {
            if (!notifications || notifications.length === 0) {
                const notifyBlock = $('#notify_block');
                if (notifyBlock.length) {
                    notifyBlock.fadeOut(300);
                }
                return;
            }
            
            // Создаем HTML для уведомлений
            let alertsHtml = '';
            notifications.forEach((notif) => {
                alertsHtml += this.createNotifyHTML(notif);
            });
            
            const notifyBlock = $('#notify_block');
            
            if (notifyBlock.length === 0) {
                // Создаем блок, если его нет
                const notifyHtml = `
                    <div id="notify_block">
                        <div class="card mb-2">
                            <div class="card-header d-flex text-dark bg-warning">
                                <h5 class="mb-0 d-flex justify-content-between align-items-center w-100" data-bs-toggle="collapse" data-bs-target="#collapse_notify" aria-expanded="true" aria-controls="collapse_notify">
                                    <i class="fas fa-info"></i>
                                    <div class="px-3 me-auto">
                                        Уведомления - ${notifications.length}
                                    </div>
                                </h5>
                                <button class="btn btn-outline-secondary text-nowrap" onclick="if(typeof NotificationSystem !== 'undefined') NotificationSystem.readNotifyAll('${source}')">Прочитать все</button>
                            </div>
                            <div class="collapse show" id="collapse_notify">
                                <div class="card-body px-2 py-0">
                                    ${alertsHtml}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                // Вставляем блок в начало .pcoded-content (после breadcrumb, если он есть)
                const contentContainer = $('.pcoded-content');
                
                if (contentContainer.length) {
                    const breadcrumb = contentContainer.find('.breadcrumb').closest('.card');
                    if (breadcrumb.length) {
                        // Вставляем после breadcrumb
                        breadcrumb.after(notifyHtml);
                    } else {
                        // Вставляем в начало контейнера
                        contentContainer.first().prepend(notifyHtml);
                    }
                    
                    const insertedBlock = $('#notify_block');
                    if (insertedBlock.length) {
                        insertedBlock.hide().fadeIn(300);
                    }
                } else {
                    // Альтернативный контейнер
                    const altContainer = $('.pcoded-main-container, .container-fluid, main');
                    if (altContainer.length) {
                        altContainer.first().prepend(notifyHtml);
                        const insertedBlock = $('#notify_block');
                        if (insertedBlock.length) {
                            insertedBlock.hide().fadeIn(300);
                        }
                    }
                }
            } else {
                // Обновляем существующий блок
                const cardBody = notifyBlock.find('.card-body');
                if (cardBody.length === 0) {
                    return;
                }
                cardBody.hide();
                cardBody.html(alertsHtml);
                cardBody.fadeIn(300);
                this.updateNotifyBlockCounter(notifications.length);
                notifyBlock.show().css('display', 'block');
            }
        },
        
        /**
         * Отметка уведомления как прочитанного
         */
        readNotify: function(id) {
            if (!id) {
                console.error('NotificationSystem: readNotify called without id');
                return;
            }
            
            $.ajax({
                url: '/api/utils/readnotify/' + id,
                method: 'GET',
                timeout: 10000,
                success: (data) => {
                    if (data && data.success) {
                        // Удаляем элемент из DOM
                        this.removeNotifyFromDOM(id, () => {
                            this.checkAndHideNotifyBlock();
                        });
                        
                        // Показываем уведомление об успехе
                        if (typeof notificationManager !== 'undefined') {
                            notificationManager.success('Уведомление отмечено как прочитанное');
                        }
                        
                        // Обновляем индикаторы
                        this.updateNotificationIndicators();
                        
                        // Обновляем блок, если мы на странице модуля
                        const source = this.getCurrentSource();
                        if (source) {
                            this.refreshNotifyBlock(source, true);
                        }
                    }
                },
                error: (xhr, status, error) => {
                    console.error('NotificationSystem: Error reading notify:', error, xhr);
                    if (typeof notificationManager !== 'undefined') {
                        notificationManager.error('Ошибка при отметке уведомления');
                    }
                }
            });
        },
        
        /**
         * Отметка всех уведомлений как прочитанных
         */
        readNotifyAll: function(source) {
            if (!source) {
                source = this.getCurrentSource();
            }
            
            if (!source) {
                console.error('NotificationSystem: readNotifyAll called without source');
                return;
            }
            
            $.ajax({
                url: '/api/utils/readnotify/all?source=' + encodeURIComponent(source),
                method: 'GET',
                timeout: 10000,
                success: (data) => {
                    if (data && data.success) {
                        const notifyBlock = $('#notify_block');
                        if (notifyBlock.length) {
                            const alerts = notifyBlock.find('.alert');
                            if (alerts.length > 0) {
                                alerts.fadeOut(300, () => {
                                    alerts.remove();
                                    this.checkAndHideNotifyBlock();
                                });
                            } else {
                                notifyBlock.fadeOut(300, () => {
                                    notifyBlock.remove();
                                });
                            }
                        }
                        
                        // Показываем уведомление об успехе
                        if (typeof notificationManager !== 'undefined') {
                            notificationManager.success('Все уведомления отмечены как прочитанные');
                        }
                        
                        // Обновляем индикаторы
                        this.updateNotificationIndicators();
                    }
                },
                error: (xhr, status, error) => {
                    console.error('NotificationSystem: Error reading all notifies:', error, xhr);
                    if (typeof notificationManager !== 'undefined') {
                        notificationManager.error('Ошибка при отметке всех уведомлений');
                    }
                }
            });
        },
        
        /**
         * Обновление индикаторов уведомлений (с debouncing и защитой от race conditions)
         */
        updateNotificationIndicators: function(force) {
            // Если уже идет обновление и это не принудительное, добавляем в очередь
            if (this.isUpdatingIndicators && !force) {
                this.indicatorUpdateQueue.push(true);
                return;
            }
            
            // Очищаем предыдущий таймер
            if (this.indicatorTimer) {
                clearTimeout(this.indicatorTimer);
            }
            
            // Debouncing
            this.indicatorTimer = setTimeout(() => {
                this._doUpdateNotificationIndicators();
            }, this.INDICATOR_DEBOUNCE);
        },
        
        /**
         * Внутренний метод обновления индикаторов
         */
        _doUpdateNotificationIndicators: function() {
            if (this.isUpdatingIndicators) {
                return;
            }
            
            this.isUpdatingIndicators = true;
            
            $.ajax({
                url: '/api/utils/notifications/stats',
                method: 'GET',
                timeout: 10000,
                success: (data) => {
                    this.isUpdatingIndicators = false;
                    
                    if (data && data.success) {
                        this._renderNotificationIndicators(data.stats);
                    }
                    
                    // Обрабатываем очередь
                    this._processIndicatorQueue();
                },
                error: (xhr, status, error) => {
                    this.isUpdatingIndicators = false;
                    console.error('NotificationSystem: Error updating indicators:', error, xhr);
                    
                    // Обрабатываем очередь даже при ошибке
                    this._processIndicatorQueue();
                }
            });
        },
        
        /**
         * Обработка очереди обновления индикаторов
         */
        _processIndicatorQueue: function() {
            if (this.indicatorUpdateQueue.length > 0) {
                this.indicatorUpdateQueue.shift();
                setTimeout(() => {
                    this.updateNotificationIndicators(true);
                }, this.INDICATOR_DEBOUNCE);
            }
        },
        
        /**
         * Рендеринг индикаторов уведомлений
         */
        _renderNotificationIndicators: function(stats) {
            // Обновление индикатора в navbar
            const navbarIndicator = $('#unreadNotifyIndicator');
            if (stats.unread > 0) {
                navbarIndicator.show();
            } else {
                navbarIndicator.hide();
            }
            
            // Обновление индикаторов в sidebar
            $('.sidebar .badge.bg-warning').hide();
            
            if (stats.sources && stats.sources.length > 0) {
                // Создаем карту источников для быстрого поиска
                const sourceMap = {};
                stats.sources.forEach((sourceStat) => {
                    if (sourceStat.source) {
                        sourceMap[sourceStat.source] = sourceStat.unread;
                    }
                });
                
                // Обновляем бейджи для каждого модуля
                $('.sidebar a[data-module-name]').each(function() {
                    const moduleName = $(this).attr('data-module-name');
                    const unreadCount = sourceMap[moduleName] || 0;
                    let badge = $(this).find('.badge.bg-warning');
                    
                    if (unreadCount > 0) {
                        if (badge.length === 0) {
                            // Создаем новый бейдж, если его нет
                            badge = $('<span class="badge bg-warning text-black rounded-pill mt-1" data-notify-count="' + unreadCount + '"></span>');
                            $(this).append(badge);
                        }
                        badge.text(unreadCount).attr('data-notify-count', unreadCount).show();
                    } else {
                        // Скрываем бейдж, если уведомлений нет
                        badge.hide();
                    }
                });
            }
        }
    };
    
    // Инициализация при загрузке DOM
    $(document).ready(function() {
        NotificationSystem.init();
        
        // Обновляем индикаторы при загрузке страницы
        NotificationSystem.updateNotificationIndicators();
        
        // Пытаемся обновить блок уведомлений для текущей страницы
        const source = NotificationSystem.getCurrentSource();
        
        if (source) {
            // Небольшая задержка для гарантии полной загрузки страницы
            setTimeout(function() {
                NotificationSystem.refreshNotifyBlock(source, true);
            }, 200);
        }
        
        // Периодическое обновление индикаторов каждые 30 секунд
        setInterval(function() {
            NotificationSystem.updateNotificationIndicators();
        }, 30000);
    });
    
    // Экспорт в глобальную область видимости
    window.NotificationSystem = NotificationSystem;
    
})();

