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

    const i18n = window.NotificationSystemI18n || {};
    const t = function(key, fallback) {
        return i18n[key] || fallback;
    };

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
            const currentPath = window.location.pathname;
            
            // Если мы на странице /admin (контрольная панель), возвращаем 'admin'
            if (currentPath === '/admin' || currentPath.endsWith('/admin')) {
                return 'admin';
            }
            
            // Если путь вида /admin/moduleName, возвращаем moduleName
            if (currentPath.includes('/admin/')) {
                const adminIndex = pathParts.indexOf('admin');
                if (adminIndex >= 0 && adminIndex < pathParts.length - 1) {
                    return pathParts[adminIndex + 1];
                }
            }
            
            // Иначе возвращаем последний элемент пути
            const source = pathParts[pathParts.length - 1];
            
            // Проверяем, что это не пустая строка
            if (!source || source === '') {
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
         * Разбор params уведомления
         */
        parseNotifyParams: function(notif) {
            if (!notif || !notif.params) {
                return {};
            }
            if (typeof notif.params === 'string') {
                try {
                    const parsed = JSON.parse(notif.params);
                    return (parsed && typeof parsed === 'object') ? parsed : {};
                } catch (e) {
                    return {};
                }
            }
            return (typeof notif.params === 'object') ? notif.params : {};
        },

        /**
         * Стили категории уведомления (Bootstrap alert colors)
         */
        getNotifyCategoryStyle: function(category) {
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
            return {
                color: categoryColors[category] || 'danger',
                icon: categoryIcons[category] || 'fas fa-info-circle'
            };
        },

        /**
         * HTML дополнительных данных уведомления (detail, error, image)
         */
        renderNotifyParamsContentHTML: function(notif) {
            const params = this.parseNotifyParams(notif);
            const parts = [];
            const detail = params.detail || params.details || '';
            const error = params.error || params.error_details || '';
            const image = params.image || params.image_url || '';

            if (detail && detail !== notif.description) {
                parts.push('<div class="small text-muted mb-1">' + this.escapeHtml(detail) + '</div>');
            }
            if (error) {
                parts.push('<div class="alert alert-danger py-1 px-2 mb-1 small">' + this.escapeHtml(error) + '</div>');
            }
            if (image) {
                parts.push(
                    '<div class="mt-2">' +
                    '<a href="' + this.escapeHtml(image) + '" target="_blank" rel="noopener">' +
                    '<img src="' + this.escapeHtml(image) + '" class="img-fluid rounded" alt="" loading="lazy" style="max-height:180px">' +
                    '</a></div>'
                );
            }
            return parts.join('');
        },

        /**
         * Кнопка перехода по params.url
         */
        renderNotifyParamsLinkButtonHTML: function(notif, className) {
            const params = this.parseNotifyParams(notif);
            const url = params.url || params.link || '';
            if (!url) {
                return '';
            }
            const label = params.label || t('open_link', 'Open link');
            const btnClass = className || 'btn btn-sm btn-outline-primary text-nowrap';
            return (
                '<a href="' + this.escapeHtml(url) + '" class="' + btnClass + '" title="' + this.escapeHtml(label) + '">' +
                '<i class="fas fa-link me-1" aria-hidden="true"></i>' + this.escapeHtml(label) +
                '</a>'
            );
        },
        
        /**
         * Поиск элемента уведомления по ID (унифицированный метод)
         */
        findNotifyElement: function(id) {
            if (!id) return $();
            
            // Пробуем несколько способов поиска
            let element = $('[data-notify-id="' + id + '"]');
            
            if (element.length === 0) {
                element = $('button[onclick*="readNotify(' + id + ')"]').closest('[data-notify-id], .alert');
            }
            
            return element;
        },

        /**
         * Проверка, что мы на контрольной панели (/admin)
         */
        isControlPanelPage: function() {
            const currentPath = window.location.pathname;
            return currentPath === '/admin' || currentPath.endsWith('/admin');
        },

        /**
         * URL модуля-источника уведомления
         */
        getSourceUrl: function(source) {
            if (!source || source === 'osysHome' || source === 'admin' || source === 'core') {
                return '/admin';
            }
            return '/admin/' + encodeURIComponent(source);
        },

        /**
         * Проверка, что source соответствует реальному модулю в системе
         */
        isRealModuleSource: function(source) {
            if (!source || source === 'osysHome' || source === 'admin' || source === 'core') {
                return false;
            }
            const modules = window.NotificationSystemModules;
            if (Array.isArray(modules) && modules.length > 0) {
                return modules.indexOf(source) >= 0;
            }
            return $('.sidebar a[data-module-name="' + source.replace(/"/g, '\\"') + '"]').length > 0;
        },

        /**
         * Source относится к блоку уведомлений контрольной панели
         * (не привязан к модулю в сайдбаре)
         */
        belongsToControlPanel: function(source) {
            return !this.isRealModuleSource(source);
        },

        /**
         * Открыть модальное окно со списком уведомлений
         */
        openNotificationsModal: function() {
            const modalEl = document.getElementById('notificationsModal');
            if (!modalEl) {
                console.error('NotificationSystem: notificationsModal not found');
                return;
            }

            this.refreshNotificationsModal();

            if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                bootstrap.Modal.getOrCreateInstance(modalEl).show();
            } else if (typeof $ !== 'undefined' && $.fn.modal) {
                $(modalEl).modal('show');
            }
        },

        /**
         * Загрузить и отрисовать уведомления в модальном окне
         */
        refreshNotificationsModal: function() {
            const body = $('#notificationsModalBody');
            const readAllBtn = $('#notificationsModalReadAll');
            if (body.length === 0) {
                return;
            }

            body.html(
                '<div class="text-center text-muted py-4">' +
                '<i class="fa-solid fa-spinner fa-spin me-2"></i>' +
                this.escapeHtml(t('loading', 'Loading...')) +
                '</div>'
            );
            readAllBtn.prop('disabled', true);

            $.ajax({
                url: '/api/utils/notifications',
                method: 'GET',
                data: { unread_only: true },
                timeout: 10000,
                success: (data) => {
                    if (data && data.success && data.notifications && data.notifications.length > 0) {
                        this._renderNotificationsModal(data.notifications);
                        readAllBtn.prop('disabled', false);
                    } else {
                        body.html(
                            '<div class="text-center text-muted py-4">' +
                            '<i class="fas fa-bell-slash me-2"></i>' +
                            this.escapeHtml(t('no_unread_notifications', 'No unread notifications')) +
                            '</div>'
                        );
                        readAllBtn.prop('disabled', true);
                    }
                },
                error: (xhr, status, error) => {
                    console.error('NotificationSystem: Error loading notifications modal:', error, xhr);
                    body.html(
                        '<div class="alert alert-danger mb-0">' +
                        this.escapeHtml(t('error_loading_notifications', 'Error loading notifications')) +
                        '</div>'
                    );
                    readAllBtn.prop('disabled', true);
                }
            });
        },

        /**
         * HTML одной карточки уведомления для модального окна
         */
        createModalNotifyHTML: function(notif) {
            const style = this.getNotifyCategoryStyle(notif.category);
            const color = style.color;
            const icon = style.icon;
            const countBadge = notif.count > 1 ?
                `<span class="badge text-bg-danger rounded-pill" title="${notif.count} ${this.escapeHtml(t('counts', 'counts'))}">${notif.count}</span>` : '';
            const createdDate = notif.created ? new Date(notif.created).toLocaleString() : '';
            const lastUpdatedDate = notif.last_updated ? new Date(notif.last_updated).toLocaleString() : '';
            let dateInfo = `<i class="fas fa-calendar-plus me-1" title="${this.escapeHtml(t('created', 'Created'))}"></i>${createdDate}`;
            if (lastUpdatedDate && notif.count && notif.count > 1) {
                dateInfo += ` <i class="fas fa-clock me-1 ms-2" title="${this.escapeHtml(t('last_updated', 'Last updated'))}"></i>${lastUpdatedDate}`;
            }

            const source = notif.source || '';
            const sourceUrl = this.getSourceUrl(source);
            const sourceLabel = source || 'osysHome';
            const isRealModule = this.isRealModuleSource(source);
            const descriptionHtml = notif.description ?
                `<div class="small mb-1">${this.escapeHtml(notif.description)}</div>` : '';
            const sourceBadgeHtml = isRealModule
                ? `<a href="${sourceUrl}" class="badge text-bg-secondary text-decoration-none" title="${this.escapeHtml(t('go_to_module', 'Go to module'))}">
                    <i class="fas fa-puzzle-piece me-1"></i>${this.escapeHtml(sourceLabel)}
                </a>`
                : `<span class="badge text-bg-secondary">
                    <i class="fas fa-puzzle-piece me-1"></i>${this.escapeHtml(sourceLabel)}
                </span>`;
            const goToModuleButtonHtml = isRealModule
                ? `<a href="${sourceUrl}" class="btn btn-sm btn-outline-primary text-nowrap" title="${this.escapeHtml(t('go_to_module', 'Go to module'))}">
                    <i class="fas fa-external-link-alt me-1" aria-hidden="true"></i>${this.escapeHtml(t('go_to_module', 'Go to module'))}
                </a>`
                : '';
            const paramsLinkButtonHtml = this.renderNotifyParamsLinkButtonHTML(notif);
            const paramsContentHtml = this.renderNotifyParamsContentHTML(notif);
            const confirmLabel = this.escapeHtml(t('confirm', 'Confirm'));

            return `
                <div class="alert alert-${color} mb-2" role="alert" data-notify-id="${notif.id}" data-notify-source="${this.escapeHtml(source)}">
                    <div class="d-flex align-items-start gap-2">
                        <i class="${icon} flex-shrink-0 mt-1"></i>
                        <div class="flex-grow-1 min-width-0">
                            <div class="d-flex flex-column flex-md-row align-items-md-start justify-content-md-between gap-2">
                                <div class="flex-grow-1 min-width-0">
                                    <div class="d-flex flex-wrap align-items-center gap-2 mb-1">
                                        ${countBadge}
                                        <strong class="mb-0">${this.escapeHtml(notif.name)}</strong>
                                        ${sourceBadgeHtml}
                                    </div>
                                    ${descriptionHtml}
                                    ${paramsContentHtml}
                                    <div class="small text-muted">${dateInfo}</div>
                                </div>
                                <div class="d-flex flex-wrap gap-2 justify-content-end">
                                    <button type="button" class="btn btn-sm btn-outline-success text-nowrap" title="${confirmLabel}" aria-label="${confirmLabel}" onclick="if(typeof NotificationSystem !== 'undefined') NotificationSystem.readNotify(${notif.id})">
                                        <i class="fas fa-check me-1" aria-hidden="true"></i>${confirmLabel}
                                    </button>
                                    ${paramsLinkButtonHtml}
                                    ${goToModuleButtonHtml}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        },

        /**
         * Рендеринг списка уведомлений в модальном окне
         */
        _renderNotificationsModal: function(notifications) {
            const body = $('#notificationsModalBody');
            if (body.length === 0) {
                return;
            }

            let html = '';
            notifications.forEach((notif) => {
                html += this.createModalNotifyHTML(notif);
            });
            body.html(html);
        },

        /**
         * Проверка и очистка модального списка, если пуст
         */
        checkAndHideNotificationsModalList: function() {
            const body = $('#notificationsModalBody');
            if (body.length === 0) {
                return;
            }

            const remaining = body.find('[data-notify-id]');
            if (remaining.length === 0) {
                body.html(
                    '<div class="text-center text-muted py-4">' +
                    '<i class="fas fa-bell-slash me-2"></i>' +
                    this.escapeHtml(t('no_unread_notifications', 'No unread notifications')) +
                    '</div>'
                );
                $('#notificationsModalReadAll').prop('disabled', true);
            }
        },
        
        /**
         * Обновление счетчика уведомлений в блоке
         */
        updateNotifyBlockCounter: function(count) {
            const notifyBlock = $('#notify_block');
            if (notifyBlock.length === 0) return;
            
            const countElement = notifyBlock.find('.px-3.me-auto');
            const notifyText = notifyBlock.find('.px-3.me-auto').text().split(' - ')[0] || t('notifications', 'Notifications');
            
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
            const style = this.getNotifyCategoryStyle(notif.category);
            const color = style.color;
            const icon = style.icon;
            const countBadge = notif.count > 1 ? 
                `<span class="badge text-bg-danger rounded-pill me-2" title="${notif.count} ${this.escapeHtml(t('counts', 'counts'))}">${notif.count}</span>` : '';
            const createdDate = notif.created ? new Date(notif.created).toLocaleString() : '';
            const lastUpdatedDate = notif.last_updated ? new Date(notif.last_updated).toLocaleString() : '';
            let dateInfo = `<i class="fas fa-calendar-plus me-1" title="${this.escapeHtml(t('created', 'Created'))}"></i>${createdDate}`;
            if (lastUpdatedDate && notif.count && notif.count > 1) {
                dateInfo += ` <i class="fas fa-clock me-1" title="${this.escapeHtml(t('last_updated', 'Last updated'))}"></i>${lastUpdatedDate}`;
            }
            
            const descriptionHtml = notif.description ? 
                `<span class="ms-1">${this.escapeHtml(notif.description)}</span>` : '';
            const source = notif.source || '';
            const sourceBadge = source && source !== this.getCurrentSource()
                ? `<span class="badge text-bg-secondary ms-1">${this.escapeHtml(source)}</span>`
                : '';
            const paramsContentHtml = this.renderNotifyParamsContentHTML(notif);
            const paramsLinkHtml = this.renderNotifyParamsLinkButtonHTML(notif, 'btn btn-sm btn-outline-primary mt-2');
            
            return `
                <div class="alert alert-${color} alert-dismissible fade show p-2 my-1" role="alert" data-notify-id="${notif.id}" data-notify-source="${this.escapeHtml(source)}">
                    <button type="button" class="btn-close" onclick="if(typeof NotificationSystem !== 'undefined') NotificationSystem.readNotify(${notif.id})" data-bs-dismiss="alert" aria-label="${this.escapeHtml(t('close', 'Close'))}"></button>
                    <div class="d-flex align-items-start gap-2 pe-3">
                        <i class="${icon} mt-1 flex-shrink-0"></i>
                        <div class="flex-grow-1 min-width-0">
                            <div>
                                ${countBadge}
                                <b>${this.escapeHtml(notif.name)}</b>
                                ${sourceBadge}
                                ${descriptionHtml}
                            </div>
                            ${paramsContentHtml}
                            ${paramsLinkHtml}
                            <div class="small text-muted mt-1">${dateInfo}</div>
                        </div>
                    </div>
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

            const isControlPanel = source === 'admin' || this.isControlPanelPage();
            const requestData = {
                unread_only: true
            };
            if (isControlPanel) {
                requestData.control_panel = 'true';
            } else {
                requestData.source = source;
            }
            
            $.ajax({
                url: '/api/utils/notifications',
                method: 'GET',
                data: requestData,
                timeout: 10000,
                success: (data) => {
                    this.isRefreshing = false;
                    
                    if (data && data.success && data.notifications) {
                        let notifications = data.notifications;
                        // Доп. фильтр на клиенте: не показывать уведомления модулей на КП
                        if (isControlPanel) {
                            notifications = notifications.filter((notif) => {
                                return this.belongsToControlPanel(notif.source || '');
                            });
                        }
                        this._renderNotifyBlock(isControlPanel ? 'admin' : source, notifications, isControlPanel);
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
        _renderNotifyBlock: function(source, notifications, isControlPanel) {
            if (!notifications || notifications.length === 0) {
                const notifyBlock = $('#notify_block');
                if (notifyBlock.length) {
                    notifyBlock.fadeOut(300);
                }
                return;
            }

            isControlPanel = !!isControlPanel || source === 'admin' || this.isControlPanelPage();
            const readAllCall = isControlPanel
                ? "NotificationSystem.readNotifyAll(null, true)"
                : "NotificationSystem.readNotifyAll('" + source + "')";
            
            // Создаем HTML для уведомлений
            let alertsHtml = '';
            notifications.forEach((notif) => {
                alertsHtml += this.createNotifyHTML(notif);
            });
            
            const notifyBlock = $('#notify_block');
            
            if (notifyBlock.length === 0) {
                // Создаем блок, если его нет
                const notifyHtml = `
                    <div id="notify_block" data-notify-mode="${isControlPanel ? 'control_panel' : 'module'}">
                        <div class="card mb-2">
                            <div class="card-header d-flex text-dark bg-warning">
                                <h5 class="mb-0 d-flex justify-content-between align-items-center w-100" data-bs-toggle="collapse" data-bs-target="#collapse_notify" aria-expanded="true" aria-controls="collapse_notify">
                                    <i class="fas fa-info"></i>
                                    <div class="px-3 me-auto">
                                        ${t('notifications', 'Notifications')} - ${notifications.length}
                                    </div>
                                </h5>
                                <button class="btn btn-outline-secondary text-nowrap" onclick="if(typeof NotificationSystem !== 'undefined') ${readAllCall}">${t('read_all', 'Read all')}</button>
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
                notifyBlock.attr('data-notify-mode', isControlPanel ? 'control_panel' : 'module');
                const readAllBtn = notifyBlock.find('button').filter(function() {
                    return ($(this).attr('onclick') || '').indexOf('readNotifyAll') >= 0;
                });
                if (readAllBtn.length) {
                    readAllBtn.attr('onclick', "if(typeof NotificationSystem !== 'undefined') " + readAllCall);
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
                        // Удаляем элемент из DOM (блок на странице и модальное окно)
                        this.removeNotifyFromDOM(id, () => {
                            this.checkAndHideNotifyBlock();
                            this.checkAndHideNotificationsModalList();
                        });
                        
                        // Показываем уведомление об успехе
                        if (typeof notificationManager !== 'undefined') {
                            notificationManager.success(t('notification_marked_read', 'Notification marked as read'));
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
                        notificationManager.error(t('error_marking_notification', 'Error marking notification'));
                    }
                }
            });
        },
        
        /**
         * Отметка всех уведомлений как прочитанных
         */
        readNotifyAll: function(source, controlPanel) {
            // source optional: если не передан — отмечаем все (модалка)
            // controlPanel: уведомления контрольной панели (не привязанные к модулям)
            if (controlPanel === undefined) {
                controlPanel = source === 'admin' && this.isControlPanelPage();
            }

            let url = '/api/utils/readnotify/all';
            if (controlPanel) {
                url += '?control_panel=true';
            } else if (source) {
                url += '?source=' + encodeURIComponent(source);
            }
            
            $.ajax({
                url: url,
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

                        if (controlPanel) {
                            const modalItems = $('#notificationsModalBody [data-notify-id]').filter((_, el) => {
                                return this.belongsToControlPanel($(el).attr('data-notify-source') || '');
                            });
                            if (modalItems.length > 0) {
                                modalItems.fadeOut(300, () => {
                                    modalItems.remove();
                                    this.checkAndHideNotificationsModalList();
                                });
                            }
                        } else {
                            const modalSelector = source
                                ? '#notificationsModalBody [data-notify-id][data-notify-source="' + source.replace(/"/g, '\\"') + '"]'
                                : '#notificationsModalBody [data-notify-id]';
                            const modalItems = $(modalSelector);
                            if (modalItems.length > 0) {
                                modalItems.fadeOut(300, () => {
                                    modalItems.remove();
                                    this.checkAndHideNotificationsModalList();
                                });
                            } else if ($('#notificationsModal').hasClass('show') && !source) {
                                this.checkAndHideNotificationsModalList();
                            }
                        }
                        
                        // Показываем уведомление об успехе
                        if (typeof notificationManager !== 'undefined') {
                            notificationManager.success(t('all_notifications_marked_read', 'All notifications marked as read'));
                        }
                        
                        // Обновляем индикаторы
                        this.updateNotificationIndicators();
                    }
                },
                error: (xhr, status, error) => {
                    console.error('NotificationSystem: Error reading all notifies:', error, xhr);
                    if (typeof notificationManager !== 'undefined') {
                        notificationManager.error(t('error_marking_all_notifications', 'Error marking all notifications'));
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
            const navbarIndicatorCompact = $('#unreadNotifyIndicatorCompact');
            if (stats.unread > 0) {
                navbarIndicator.removeClass('d-none').addClass('d-flex');
                navbarIndicatorCompact.removeClass('d-none');
            } else {
                navbarIndicator.addClass('d-none').removeClass('d-flex');
                navbarIndicatorCompact.addClass('d-none');
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

