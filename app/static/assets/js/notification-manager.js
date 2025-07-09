class NotificationManager {  
    constructor() {  
        this.notifications = new Map();  
        this.settings = {  
            maxNotifications: 5,  
            defaultDuration: 10000,  
            positions: ['top-end', 'top-start', 'bottom-end', 'bottom-start'],  
            currentPosition: 'top-end'  
        };  
        this.queue = [];  
        this.init();  
    }  
  
    init() {  
        // Создаем контейнеры для разных позиций  
        this.settings.positions.forEach(position => {  
            if (!document.querySelector(`.toast-container-${position}`)) {  
                const container = document.createElement('div');  
                container.className = `toast-container toast-container-${position} position-fixed p-3`;  
                container.style.zIndex = '1055';  
                this.setContainerPosition(container, position);  
                document.body.appendChild(container);  
            }  
        });  
    }  
  
    setContainerPosition(container, position) {  
        const positions = {  
            'top-end': { top: '20px', right: '20px' },  
            'top-start': { top: '20px', left: '20px' },  
            'bottom-end': { bottom: '20px', right: '20px' },  
            'bottom-start': { bottom: '20px', left: '20px' }  
        };  
          
        Object.assign(container.style, positions[position]);  
    }  
  
    show(data, options = {}) {  
        const config = {  
            level: data.level || 'info',  
            message: data.message || '',  
            title: data.title || 'Уведомление',  
            duration: options.duration || this.getDurationByLevel(data.level),  
            position: options.position || this.settings.currentPosition,  
            persistent: options.persistent || false,  
            actions: options.actions || [],  
            groupKey: options.groupKey || null,  
            sound: options.sound || false  
        };  
  
        // Группировка похожих уведомлений  
        if (config.groupKey && this.notifications.has(config.groupKey)) {  
            this.updateGroupedNotification(config.groupKey, config);  
            return;  
        }  
  
        // Проверка лимита уведомлений  
        if (this.notifications.size >= this.settings.maxNotifications) {  
            this.queue.push(config);  
            return;  
        }  
  
        this.createNotification(config);  
    }  
  
    getDurationByLevel(level) {  
        const durations = {  
            'error': 15000,  
            'warning': 12000,  
            'success': 8000,  
            'info': 10000,  
            'debug': 5000  
        };  
        return durations[level] || 10000;  
    }  
  
    createNotification(config) {  
        const notificationId = this.generateId();  
        const toast = this.buildToastHTML(notificationId, config);  
          
        const container = document.querySelector(`.toast-container-${config.position}`);  
        container.insertAdjacentHTML('beforeend', toast);  
          
        const toastElement = container.querySelector(`#toast-${notificationId}`);  
        const bsToast = new bootstrap.Toast(toastElement, {
            autohide: config.persistent,
            delay: config.persistent ? 999999999 : config.duration  
        });  
  
        this.notifications.set(notificationId, {  
            element: toastElement,  
            bsToast: bsToast,  
            config: config  
        });  
  
        // Показываем уведомление  
        bsToast.show();  
  
        // Воспроизводим звук если нужно  
        if (config.sound) {  
            this.playNotificationSound(config.level);  
        }  
  
        // Автоудаление  
        if (!config.persistent) {  
            setTimeout(() => {  
                this.remove(notificationId);  
            }, config.duration + 1000);  
        }  
  
        // Обработчики событий  
        this.attachEventHandlers(notificationId, toastElement);  
    }  
  
    buildToastHTML(id, config) {  
        const levelIcons = {  
            'error': 'fas fa-exclamation-circle',  
            'warning': 'fas fa-exclamation-triangle',   
            'success': 'fas fa-check-circle',  
            'info': 'fas fa-info-circle',  
            'debug': 'fas fa-bug'  
        };  
  
        const levelColors = {  
            'error': 'danger',  
            'warning': 'warning',  
            'success': 'success',   
            'info': 'primary',  
            'debug': 'secondary'  
        };  
  
        const actionsHTML = config.actions.map(action =>   
            `<button type="button" class="btn btn-sm btn-outline-${levelColors[config.level]} me-2"   
                     onclick="notificationManager.handleAction('${id}', '${action.id}')">${action.label}</button>`  
        ).join('');  
  
        const now = new Date();  
        const timeString = now.toLocaleTimeString('ru-RU', {   
            hour: '2-digit',   
            minute: '2-digit',   
            second: '2-digit'   
        });  
  
        return `  
            <div id="toast-${id}" class="toast notification-toast notification-${config.level}"   
                 role="alert" aria-live="assertive" aria-atomic="true">  
                <div class="toast-header">  
                    <i class="${levelIcons[config.level]} text-${levelColors[config.level]} me-2"></i>  
                    <strong class="me-auto">${config.title}</strong>  
                    <small class="text-muted">${timeString}</small>  
                    ${config.persistent ? '' : '<button type="button" class="btn-close" data-bs-dismiss="toast"></button>'}  
                </div>  
                <div class="toast-body">  
                    <div class="notification-message">${config.message}</div>  
                    ${actionsHTML ? `<div class="notification-actions mt-2">${actionsHTML}</div>` : ''}  
                </div>  
            </div>  
        `;  
    }  
  
    updateGroupedNotification(groupKey, config) {  
        const notification = this.notifications.get(groupKey);  
        if (!notification) return;  
  
        const countElement = notification.element.querySelector('.notification-count');  
        const currentCount = parseInt(countElement?.textContent || '1') + 1;  
          
        if (countElement) {  
            countElement.textContent = currentCount;  
        } else {  
            const header = notification.element.querySelector('.toast-header strong');  
            header.insertAdjacentHTML('afterend',   
                `<span class="badge bg-danger rounded-pill ms-2 notification-count">${currentCount}</span>`  
            );  
        }  
  
        // Обновляем сообщение  
        const messageElement = notification.element.querySelector('.notification-message');  
        messageElement.textContent = config.message;  
  
        // Перезапускаем таймер если не persistent  
        if (!notification.config.persistent) {  
            notification.bsToast.hide();  
            setTimeout(() => notification.bsToast.show(), 100);  
        }  
    }  
  
    handleAction(notificationId, actionId) {  
        const notification = this.notifications.get(notificationId);  
        if (!notification) return;  
  
        // Вызываем callback действия  
        const action = notification.config.actions.find(a => a.id === actionId);  
        if (action && action.callback) {  
            action.callback(notificationId, actionId);  
        }  
  
        // Закрываем уведомление если не указано иное  
        if (!action || action.closeOnClick !== false) {  
            this.remove(notificationId);  
        }  
    }  
  
    remove(notificationId) {  
        const notification = this.notifications.get(notificationId);  
        if (!notification) return;  
  
        notification.bsToast.hide();  
        setTimeout(() => {  
            notification.element.remove();  
            this.notifications.delete(notificationId);  
            this.processQueue();  
        }, 300);  
    }  
  
    processQueue() {  
        if (this.queue.length > 0 && this.notifications.size < this.settings.maxNotifications) {  
            const config = this.queue.shift();  
            this.createNotification(config);  
        }  
    }  
  
    attachEventHandlers(notificationId, element) {  
        // Пауза при наведении  
        element.addEventListener('mouseenter', () => {  
            const notification = this.notifications.get(notificationId);  
            if (notification && !notification.config.persistent) {  
                notification.bsToast._config.delay = false;  
            }  
        });  
  
        element.addEventListener('mouseleave', () => {  
            const notification = this.notifications.get(notificationId);  
            if (notification && !notification.config.persistent) {  
                notification.bsToast._config.delay = notification.config.duration;  
            }  
        });  
  
        // Обработка закрытия  
        element.addEventListener('hidden.bs.toast', () => {  
            this.remove(notificationId);  
        });  
    }  
  
    playNotificationSound(level) {  
        // Интеграция с существующей системой звуков  
        if (typeof playSound === 'function') {  
            const soundFiles = {  
                'error': '/static/assets/sounds/error.wav',  
                'warning': '/static/assets/sounds/warning.wav',   
                'success': '/static/assets/sounds/success.wav',  
                'info': '/static/assets/sounds/info.mp3'  
            };  
            playSound(soundFiles[level] || '/static/assets/sounds/info.mp3');  
        }  
    }  
  
    generateId() {  
        return 'notif_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);  
    }  
  
    // Публичные методы для разных типов уведомлений  
    success(message, options = {}) {  
        this.show({ level: 'success', message, title: 'Успех' }, options);  
    }  
  
    error(message, options = {}) {  
        this.show({ level: 'error', message, title: 'Ошибка' }, options);  
    }  
  
    warning(message, options = {}) {  
        this.show({ level: 'warning', message, title: 'Предупреждение' }, options);  
    }  
  
    info(message, options = {}) {  
        this.show({ level: 'info', message, title: 'Информация' }, options);  
    }  
  
    // Очистка всех уведомлений  
    clear() {  
        this.notifications.forEach((notification, id) => {  
            this.remove(id);  
        });  
        this.queue = [];  
    }  
}  
  
// Глобальный экземпляр  
const notificationManager = new NotificationManager();