(function(global) {
  'use strict';

  var modalEl = null;
  var modalInstance = null;
  var pendingResolve = null;
  var i18n = global.ConfirmModalI18n || {};

  var alertModalEl = null;
  var alertModalInstance = null;
  var alertPendingResolve = null;
  var alertQueue = [];
  var alertI18n = global.AlertModalI18n || {};

  function getModal() {
    if (!modalEl) {
      modalEl = document.getElementById('appConfirmModal');
    }
    return modalEl;
  }

  function getInstance() {
    if (typeof bootstrap === 'undefined') {
      return null;
    }
    var el = getModal();
    if (!el) {
      return null;
    }
    if (!modalInstance) {
      modalInstance = bootstrap.Modal.getOrCreateInstance(el, {
        backdrop: 'static',
        keyboard: false
      });
    }
    return modalInstance;
  }

  function getAlertModal() {
    if (!alertModalEl) {
      alertModalEl = document.getElementById('appAlertModal');
    }
    return alertModalEl;
  }

  function getAlertInstance() {
    if (typeof bootstrap === 'undefined') {
      return null;
    }
    var el = getAlertModal();
    if (!el) {
      return null;
    }
    if (!alertModalInstance) {
      alertModalInstance = bootstrap.Modal.getOrCreateInstance(el, {
        backdrop: 'static',
        keyboard: false
      });
    }
    return alertModalInstance;
  }

  function closeOpenDropdowns(triggerEl) {
    if (typeof bootstrap === 'undefined') {
      return;
    }
    var dropdownRoot = triggerEl && triggerEl.closest ? triggerEl.closest('.dropdown') : null;
    if (dropdownRoot) {
      var toggle = dropdownRoot.querySelector('[data-bs-toggle="dropdown"]');
      var dropdown = toggle ? bootstrap.Dropdown.getInstance(toggle) : null;
      if (dropdown) {
        dropdown.hide();
      }
    }
    document.querySelectorAll('.dropdown-menu.show').forEach(function(menu) {
      menu.classList.remove('show');
    });
  }

  function isDangerMessage(message) {
    return /delete|remove|clear|drop|удал|очист|сброс/i.test(message || '');
  }

  function setModalHeaderIcon(iconEl, kind, danger) {
    if (!iconEl) {
      return;
    }
    var icons = {
      confirm: {
        normal: ['fa-circle-question', 'text-primary'],
        danger: ['fa-triangle-exclamation', 'text-danger']
      },
      alert: {
        normal: ['fa-circle-info', 'text-primary'],
        danger: ['fa-circle-exclamation', 'text-danger']
      }
    };
    var config = icons[kind] && icons[kind][danger ? 'danger' : 'normal'];
    if (!config) {
      return;
    }
    iconEl.className = 'fas ' + config[0] + ' me-2 ' + config[1];
  }

  function decodeJsString(str) {
    return String(str || '')
      .replace(/\\n/g, '\n')
      .replace(/\\r/g, '\r')
      .replace(/\\t/g, '\t')
      .replace(/\\'/g, "'")
      .replace(/\\"/g, '"')
      .replace(/\\\\/g, '\\');
  }

  function extractConfirmFromHandler(handler) {
    if (!handler || handler.indexOf('confirm(') === -1) {
      return null;
    }

    var returnMatch = handler.match(/return\s+confirm\s*\(\s*(['"`])((?:\\.|(?!\1).)*)\1\s*\)/);
    if (returnMatch) {
      return { type: 'return', message: decodeJsString(returnMatch[2]) };
    }

    var ifMatch = handler.match(/if\s*\(\s*confirm\s*\(\s*(['"`])((?:\\.|(?!\1).)*)\1\s*\)\s*\)\s*([\s\S]+)/);
    if (ifMatch) {
      var action = ifMatch[3].trim();
      if (action.endsWith(';')) {
        action = action.slice(0, -1);
      }
      return { type: 'if', message: decodeJsString(ifMatch[2]), action: action };
    }

    return null;
  }

  function cleanupListeners(el, handlers) {
    if (!el || !handlers) {
      return;
    }
    if (handlers.onConfirm && handlers.confirmBtn) {
      handlers.confirmBtn.removeEventListener('click', handlers.onConfirm);
    }
    if (handlers.onCancel && handlers.cancelBtn) {
      handlers.cancelBtn.removeEventListener('click', handlers.onCancel);
    }
    if (handlers.onHidden) {
      el.removeEventListener('hidden.bs.modal', handlers.onHidden);
    }
    if (handlers.onShown) {
      el.removeEventListener('shown.bs.modal', handlers.onShown);
    }
  }

  function showConfirm(message, options) {
    options = options || {};
    return new Promise(function(resolve) {
      var el = getModal();
      var instance = getInstance();
      if (!el || !instance) {
        resolve(global.nativeConfirm ? global.nativeConfirm(message) : false);
        return;
      }
      if (pendingResolve) {
        resolve(false);
        return;
      }

      pendingResolve = resolve;
      var settled = false;
      var handlers = {};

      var titleEl = document.getElementById('appConfirmModalTitleText');
      var iconEl = document.getElementById('appConfirmModalIcon');
      var messageEl = document.getElementById('appConfirmModalMessage');
      var confirmBtn = document.getElementById('appConfirmModalConfirm');
      var cancelBtn = document.getElementById('appConfirmModalCancel');
      if (!confirmBtn || !cancelBtn) {
        pendingResolve = null;
        resolve(global.nativeConfirm ? global.nativeConfirm(message) : false);
        return;
      }

      handlers.confirmBtn = confirmBtn;
      handlers.cancelBtn = cancelBtn;

      var danger = options.danger;
      if (danger === undefined) {
        danger = isDangerMessage(message);
      }

      if (titleEl) {
        titleEl.textContent = options.title || i18n.title || 'Confirm';
      }
      setModalHeaderIcon(iconEl, 'confirm', danger);
      if (messageEl) {
        messageEl.textContent = message || '';
      }
      confirmBtn.textContent = options.confirmText || i18n.confirm || 'Confirm';
      confirmBtn.className = 'btn ' + (danger ? 'btn-danger' : 'btn-primary');
      cancelBtn.textContent = options.cancelText || i18n.cancel || 'Cancel';

      function settle(value) {
        if (settled || !pendingResolve) {
          return;
        }
        settled = true;
        var done = pendingResolve;
        pendingResolve = null;
        cleanupListeners(el, handlers);
        done(value);
      }

      handlers.onConfirm = function() {
        instance.hide();
        settle(true);
      };

      handlers.onCancel = function() {
        instance.hide();
        settle(false);
      };

      handlers.onHidden = function() {
        if (!settled) {
          settle(false);
        }
      };

      handlers.onShown = function() {
        global.setTimeout(function() {
          if (danger && cancelBtn) {
            cancelBtn.focus();
          } else if (confirmBtn) {
            confirmBtn.focus();
          }
        }, 0);
      };

      confirmBtn.addEventListener('click', handlers.onConfirm);
      cancelBtn.addEventListener('click', handlers.onCancel);
      el.addEventListener('hidden.bs.modal', handlers.onHidden);
      el.addEventListener('shown.bs.modal', handlers.onShown, { once: true });

      instance.show();
    });
  }

  function cleanupAlertListeners(el, handlers) {
    if (!el || !handlers) {
      return;
    }
    if (handlers.onOk && handlers.okBtn) {
      handlers.okBtn.removeEventListener('click', handlers.onOk);
    }
    if (handlers.onHidden) {
      el.removeEventListener('hidden.bs.modal', handlers.onHidden);
    }
    if (handlers.onShown) {
      el.removeEventListener('shown.bs.modal', handlers.onShown);
    }
  }

  function processAlertQueue() {
    if (alertPendingResolve || !alertQueue.length) {
      return;
    }

    var item = alertQueue.shift();
    var el = getAlertModal();
    var instance = getAlertInstance();
    if (!el || !instance) {
      if (global.nativeAlert) {
        global.nativeAlert(item.message);
      }
      item.resolve();
      processAlertQueue();
      return;
    }

    alertPendingResolve = item.resolve;
    var settled = false;
    var handlers = {};

    var titleEl = document.getElementById('appAlertModalTitleText');
    var iconEl = document.getElementById('appAlertModalIcon');
    var messageEl = document.getElementById('appAlertModalMessage');
    var okBtn = document.getElementById('appAlertModalOk');
    if (!okBtn) {
      alertPendingResolve = null;
      if (global.nativeAlert) {
        global.nativeAlert(item.message);
      }
      item.resolve();
      processAlertQueue();
      return;
    }

    handlers.okBtn = okBtn;

    var danger = item.options.danger;
    if (danger === undefined) {
      danger = item.options.error || isDangerMessage(item.message);
    }

    if (titleEl) {
      titleEl.textContent = item.options.title
        || (danger ? (alertI18n.errorTitle || 'Error') : (alertI18n.title || 'Message'));
    }
    setModalHeaderIcon(iconEl, 'alert', danger);
    if (messageEl) {
      messageEl.textContent = item.message || '';
    }
    okBtn.textContent = item.options.okText || alertI18n.ok || 'OK';
    okBtn.className = 'btn ' + (danger ? 'btn-danger' : 'btn-primary');

    function settle() {
      if (settled || !alertPendingResolve) {
        return;
      }
      settled = true;
      var done = alertPendingResolve;
      alertPendingResolve = null;
      cleanupAlertListeners(el, handlers);
      done();
      processAlertQueue();
    }

    handlers.onOk = function() {
      instance.hide();
      settle();
    };

    handlers.onHidden = function() {
      if (!settled) {
        settle();
      }
    };

    handlers.onShown = function() {
      global.setTimeout(function() {
        if (okBtn) {
          okBtn.focus();
        }
      }, 0);
    };

    okBtn.addEventListener('click', handlers.onOk);
    el.addEventListener('hidden.bs.modal', handlers.onHidden);
    el.addEventListener('shown.bs.modal', handlers.onShown, { once: true });

    instance.show();
  }

  function showAlert(message, options) {
    options = options || {};
    return new Promise(function(resolve) {
      alertQueue.push({ message: message, options: options, resolve: resolve });
      processAlertQueue();
    });
  }

  function executeConfirmedAction(element, parsed, handler) {
    if (parsed.type === 'return') {
      if (element.tagName === 'A') {
        var href = element.getAttribute('href');
        if (href && href !== '#' && href.indexOf('javascript:') !== 0) {
          global.location.assign(href);
          return;
        }
      }

      var form = element.form || (element.closest ? element.closest('form') : null);
      if (form) {
        var origSubmit = form.getAttribute('onsubmit');
        form.removeAttribute('onsubmit');
        element.removeAttribute('onclick');
        if (form.requestSubmit) {
          if (element.type === 'submit') {
            form.requestSubmit(element);
          } else {
            form.requestSubmit();
          }
        } else {
          form.submit();
        }
        if (origSubmit) {
          form.setAttribute('onsubmit', origSubmit);
        }
        element.setAttribute('onclick', handler);
        return;
      }

      element.removeAttribute('onclick');
      element.click();
      element.setAttribute('onclick', handler);
      return;
    }

    if (parsed.type === 'if' && parsed.action) {
      try {
        (0, eval)(parsed.action);
      } catch (err) {
        console.error('[confirm-modal] Action failed:', err);
      }
    }
  }

  function interceptHandler(event, element, attrName) {
    var handler = element.getAttribute(attrName);
    var parsed = extractConfirmFromHandler(handler);
    if (!parsed) {
      return false;
    }

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    closeOpenDropdowns(element);

    showConfirm(parsed.message, { danger: isDangerMessage(parsed.message) }).then(function(confirmed) {
      if (confirmed) {
        executeConfirmedAction(element, parsed, handler);
      }
    });
    return true;
  }

  document.addEventListener('click', function(event) {
    if (event.target.closest('.object-delete-action, .class-delete-action')) {
      return;
    }

    var el = event.target.closest('[onclick]');
    if (!el) {
      return;
    }
    var handler = el.getAttribute('onclick');
    if (!handler || handler.indexOf('confirm(') === -1) {
      return;
    }
    interceptHandler(event, el, 'onclick');
  }, true);

  document.addEventListener('submit', function(event) {
    var form = event.target;
    if (!form || !form.getAttribute) {
      return;
    }
    var handler = form.getAttribute('onsubmit');
    if (!handler || handler.indexOf('confirm(') === -1) {
      return;
    }

    var parsed = extractConfirmFromHandler(handler);
    if (!parsed) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    showConfirm(parsed.message, { danger: isDangerMessage(parsed.message) }).then(function(confirmed) {
      if (!confirmed) {
        return;
      }
      form.removeAttribute('onsubmit');
      if (form.requestSubmit) {
        form.requestSubmit(event.submitter || undefined);
      } else {
        form.submit();
      }
      form.setAttribute('onsubmit', handler);
    });
  }, true);

  global.nativeConfirm = global.confirm.bind(global);
  global.nativeAlert = global.alert.bind(global);
  global.showConfirm = showConfirm;
  global.showAlert = showAlert;
  global.alert = function(message) {
    showAlert(message == null ? '' : String(message));
  };
  global.closeOpenDropdowns = closeOpenDropdowns;
})(window);
