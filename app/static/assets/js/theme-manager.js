(function () {
  var STORAGE_KEY = 'ui-theme';
  var LEGACY_KEY = 'dark-theme';

  var THEMES = {
    light:       { bs: 'light', icon: 'fa-sun' },
    dark:        { bs: 'dark',  icon: 'fa-moon' },
    'dark-blue': { bs: 'dark',  icon: 'fa-water' },
    sepia:       { bs: 'light', icon: 'fa-book-open' },
    midnight:    { bs: 'dark',  icon: 'fa-star' },
    vue:         { bs: 'light', icon: 'fa-leaf' },
    'vue-dark':  { bs: 'dark',  icon: 'fa-leaf' },
    nord:        { bs: 'dark',  icon: 'fa-snowflake' },
    dracula:     { bs: 'dark',  icon: 'fa-skull' },
    catppuccin:  { bs: 'dark',  icon: 'fa-mug-hot' },
    'one-dark':  { bs: 'dark',  icon: 'fa-atom' },
    'solarized-light': { bs: 'light', icon: 'fa-sun' },
    'solarized-dark':  { bs: 'dark',  icon: 'fa-moon' },
    'gruvbox-light':   { bs: 'light', icon: 'fa-book' },
    'gruvbox-dark':    { bs: 'dark',  icon: 'fa-mountain' },
    'tokyo-night':     { bs: 'dark',  icon: 'fa-city' },
    'rose-pine':       { bs: 'dark',  icon: 'fa-spa' },
    'rose-pine-dawn':  { bs: 'light', icon: 'fa-cloud-sun' },
    'everforest-dark': { bs: 'dark',  icon: 'fa-tree' },
    'everforest-light':{ bs: 'light', icon: 'fa-tree' },
    kanagawa:          { bs: 'dark',  icon: 'fa-water' },
    'kanagawa-lotus':  { bs: 'light', icon: 'fa-fan' },
    ayu:               { bs: 'dark',  icon: 'fa-adjust' },
    'material-ocean':  { bs: 'dark',  icon: 'fa-water' },
    'monokai-pro':     { bs: 'dark',  icon: 'fa-gem' },
    'nordic-minimal':  { bs: 'dark',  icon: 'fa-snowflake' },
    'slate-dark':      { bs: 'dark',  icon: 'fa-square' },
    'cyberpunk-neon':  { bs: 'dark',  icon: 'fa-bolt' },
    'corporate-light': { bs: 'light', icon: 'fa-briefcase' },
    'warm-beige':      { bs: 'light', icon: 'fa-scroll' },
    'forest-emerald':  { bs: 'dark',  icon: 'fa-tree' },
    'high-contrast-pro': { bs: 'dark', icon: 'fa-adjust' },
    'oled-black':      { bs: 'dark',  icon: 'fa-circle' },
    'github-light':    { bs: 'light', icon: 'fa-github' },
    'github-dark':     { bs: 'dark',  icon: 'fa-github' },
    'material-3':      { bs: 'light', icon: 'fa-layer-group' }
  };

  function resolveTheme(name) {
    return THEMES[name] ? name : 'light';
  }

  function loadStoredTheme() {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return resolveTheme(stored);
    }
    if (localStorage.getItem(LEGACY_KEY) === 'true') {
      return 'dark';
    }
    return 'light';
  }

  function applyTheme(name) {
    var theme = resolveTheme(name);
    var meta = THEMES[theme];
    var body = document.querySelector('[data-tag="body"]') || document.body;
    var root = document.documentElement;
    body.setAttribute('data-bs-theme', meta.bs);
    body.setAttribute('data-ui-theme', theme);
    root.setAttribute('data-bs-theme', meta.bs);
    root.setAttribute('data-ui-theme', theme);
    body.classList.toggle('dark-mode', meta.bs === 'dark');
    localStorage.setItem(STORAGE_KEY, theme);
    document.dispatchEvent(new CustomEvent('ui-theme-changed', {
      detail: { theme: theme, bs: meta.bs }
    }));
    updateThemeButton(theme);
    syncThemeMenu(theme);
  }

  function syncThemeMenu(theme) {
    var menu = document.getElementById('uiThemeMenu');
    if (!menu) {
      return;
    }
    menu.querySelectorAll('[data-ui-theme]').forEach(function (item) {
      var active = item.getAttribute('data-ui-theme') === theme;
      item.classList.toggle('active', active);
      item.setAttribute('aria-checked', active ? 'true' : 'false');
    });
  }

  function updateThemeButton(theme) {
    var btn = document.getElementById('uiThemeSwitch');
    if (!btn) {
      return;
    }
    var meta = THEMES[theme] || THEMES.light;
    var icon = btn.querySelector('.ui-theme-icon');
    if (icon) {
      icon.className = 'fas ' + meta.icon + ' ui-theme-icon';
    }
  }

  function initThemeDropdown() {
    var menu = document.getElementById('uiThemeMenu');
    if (!menu) {
      return;
    }
    var current = loadStoredTheme();
    menu.querySelectorAll('[data-ui-theme]').forEach(function (item) {
      item.addEventListener('click', function (event) {
        event.preventDefault();
        applyTheme(item.getAttribute('data-ui-theme'));
      });
    });
    syncThemeMenu(current);
    updateThemeButton(current);
  }

  window.UIThemes = {
    THEMES: THEMES,
    loadStoredTheme: loadStoredTheme,
    applyTheme: applyTheme,
    resolveTheme: resolveTheme
  };

  document.addEventListener('DOMContentLoaded', initThemeDropdown);
})();
