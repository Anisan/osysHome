(function(global) {
  'use strict';

  var modalEl = null;
  var dialogEl = null;
  var bodyEl = null;
  var titleEl = null;
  var modalInstance = null;
  var pendingResolve = null;
  var loadToken = 0;
  var reopenOptions = null;
  var waitingForReopen = null;
  var i18n = global.ContentModalI18n || {};

  var SIZE_CLASSES = ['modal-sm', 'modal-lg', 'modal-xl'];

  function getModal() {
    if (!modalEl) {
      modalEl = document.getElementById('appContentModal');
    }
    return modalEl;
  }

  function getDialog() {
    if (!dialogEl) {
      dialogEl = document.getElementById('appContentModalDialog');
    }
    return dialogEl;
  }

  function getBody() {
    if (!bodyEl) {
      bodyEl = document.getElementById('appContentModalBody');
    }
    return bodyEl;
  }

  function getTitle() {
    if (!titleEl) {
      titleEl = document.getElementById('appContentModalTitleText');
    }
    return titleEl;
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
      modalInstance = bootstrap.Modal.getOrCreateInstance(el);
    }
    return modalInstance;
  }

  function resetDialogClasses(options) {
    var dialog = getDialog();
    if (!dialog) {
      return;
    }
    SIZE_CLASSES.forEach(function(cls) {
      dialog.classList.remove(cls);
    });
    dialog.classList.toggle('modal-dialog-centered', options.centered !== false);
    dialog.classList.toggle('modal-dialog-scrollable', options.scrollable !== false);

    var size = options.size || '';
    if (size === 'sm' || size === 'lg' || size === 'xl') {
      dialog.classList.add('modal-' + size);
    }
  }

  function setLoading() {
    var body = getBody();
    if (!body) {
      return;
    }
    var loadingText = i18n.loading || 'Loading...';
    body.innerHTML =
      '<div class="d-flex align-items-center justify-content-center py-4 text-muted" role="status">' +
      '<div class="spinner-border spinner-border-sm me-2" aria-hidden="true"></div>' +
      '<span>' + loadingText + '</span>' +
      '</div>';
  }

  function setError(message) {
    var body = getBody();
    if (!body) {
      return;
    }
    var text = message || i18n.error || 'Error loading content';
    body.innerHTML = '<div class="alert alert-danger mb-0" role="alert"></div>';
    body.firstChild.textContent = text;
  }

  function clearContent() {
    var body = getBody();
    var title = getTitle();
    var dialog = getDialog();
    if (body) {
      body.innerHTML = '';
    }
    if (title) {
      title.textContent = '';
    }
    if (dialog) {
      SIZE_CLASSES.forEach(function(cls) {
        dialog.classList.remove(cls);
      });
      dialog.classList.add('modal-dialog-centered', 'modal-dialog-scrollable');
    }
  }

  function settleClose() {
    if (!pendingResolve) {
      return;
    }
    var done = pendingResolve;
    pendingResolve = null;
    done();
  }

  function onHidden() {
    clearContent();
    settleClose();

    if (reopenOptions) {
      var next = reopenOptions;
      var deferred = waitingForReopen;
      reopenOptions = null;
      waitingForReopen = null;
      global.setTimeout(function() {
        var opened = openContentModal(next);
        if (deferred) {
          opened.then(deferred);
        }
      }, 0);
    }
  }

  function ensureHiddenListener() {
    var el = getModal();
    if (!el || el._contentModalHiddenBound) {
      return;
    }
    el.addEventListener('hidden.bs.modal', onHidden);
    el._contentModalHiddenBound = true;
  }

  function fillContent(options, token) {
    if (options.url) {
      setLoading();
      fetch(options.url, {
        credentials: 'same-origin',
        headers: { Accept: 'text/html' }
      })
        .then(function(response) {
          if (!response.ok) {
            throw new Error((i18n.error || 'Error loading content') + ' (' + response.status + ')');
          }
          return response.text();
        })
        .then(function(html) {
          if (token !== loadToken) {
            return;
          }
          var body = getBody();
          if (body) {
            body.innerHTML = html;
          }
        })
        .catch(function(err) {
          if (token !== loadToken) {
            return;
          }
          setError(err && err.message ? err.message : (i18n.error || 'Error loading content'));
        });
      return;
    }

    var body = getBody();
    if (body) {
      body.innerHTML = options.html == null ? '' : String(options.html);
    }
  }

  function isModalActive(el, instance) {
    if (!el) {
      return false;
    }
    if (el.classList.contains('show')) {
      return true;
    }
    // Во время анимации show/hide class 'show' может ещё не стоять / уже снят
    if (instance && (instance._isShown || instance._isTransitioning)) {
      return true;
    }
    return false;
  }

  function applyContent(options) {
    loadToken += 1;
    var token = loadToken;
    var title = getTitle();
    if (title) {
      title.textContent = options.title || '';
    }
    resetDialogClasses(options);
    fillContent(options, token);
    return token;
  }

  function openContentModal(options) {
    options = options || {};
    var el = getModal();
    var instance = getInstance();
    if (!el || !instance) {
      return Promise.resolve();
    }

    ensureHiddenListener();

    // Уже открыта или в transition — обновляем содержимое на месте
    // (hide→show во время анимации ломает Bootstrap Modal)
    if (isModalActive(el, instance)) {
      reopenOptions = null;
      if (waitingForReopen) {
        var skipped = waitingForReopen;
        waitingForReopen = null;
        skipped();
      }
      applyContent(options);
      return new Promise(function(resolve) {
        var prev = pendingResolve;
        pendingResolve = function() {
          if (prev) {
            prev();
          }
          resolve();
        };
      });
    }

    return new Promise(function(resolve) {
      pendingResolve = resolve;
      applyContent(options);
      instance.show();
    });
  }

  /**
   * Показать модалку с произвольным контентом.
   * options: { title, html, url, size, centered, scrollable }
   * При html и url одновременно приоритет у url.
   * Возвращает Promise, который резолвится при закрытии.
   */
  function showContentModal(options) {
    return openContentModal(options || {});
  }

  global.showContentModal = showContentModal;
})(window);
