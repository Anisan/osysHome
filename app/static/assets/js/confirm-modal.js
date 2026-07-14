(function(global) {
  'use strict';

  var modalEl = null;
  var modalInstance = null;
  var pendingResolve = null;
  var i18n = global.ConfirmModalI18n || {};

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

      var titleEl = document.getElementById('appConfirmModalTitle');
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
  global.showConfirm = showConfirm;
  global.closeOpenDropdowns = closeOpenDropdowns;
})(window);
