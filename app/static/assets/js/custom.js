  
// Функция для форматирования времени в виде строки
function formatTimeDiff(diff) {
    var second = 1000;
    var minute = 1000 * 60;
    var hour = 1000 * 60 * 60;
    var day = 1000 * 60 * 60 * 24;
    var days = Math.floor(diff / day);
    diff -= days * day;
    var hours = Math.floor(diff / hour);
    diff -= hours * hour;
    var minutes = Math.floor(diff / minute);
    diff -= minutes * minute;
    var seconds = Math.floor(diff / second);
    var text = "";
    if (days > 0) text += days + " дн. ";
    if (hours > 0) text += hours + " ч. ";
    if (days==0 && minutes > 0) text += minutes + " мин. ";
    if (days==0 && hours == 0 && seconds > 0) text += seconds + " сек. ";
    if (text == "") 
      text += "только что";
    else {
      if (this.posValue)
        text = text + this.posValue
      else {
        if (diff>0) text += "назад"; 
      }
      if (this.preValue) 
        text = this.preValue + text
      else{
        if (diff<0) text = "Осталось " + text
      }
    }
    return text.trim()
}

/** Browser IANA zone (Intl); used by .time-component wall-clock bits. */
function getBrowserTimeZone() {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
    } catch (e) {
        return undefined;
    }
}

/**
 * Parse data-start-time for .time-component.
 * Expects server-local wall time from getProperty(..., 'changed') / msg.changed.
 * Naive strings are interpreted in the browser local zone (no forced Z).
 * Values with Z/offset are still absolute instants.
 */
function parseTimeComponentStart(startTimeValue) {
    if (startTimeValue === undefined || startTimeValue === null) return NaN;
    var s = String(startTimeValue).trim();
    if (!s) return NaN;
    if (/^\d+(\.\d+)?$/.test(s)) {
        var n = parseFloat(s);
        return s.length <= 10 ? n * 1000 : n;
    }
    if (/[zZ]|[+-]\d{2}:?\d{2}$/.test(s)) {
        return Date.parse(s);
    }
    // Naive datetime → browser local (matches convert_utc_to_local for the client)
    return Date.parse(s.replace(' ', 'T'));
}

/** Absolute wall-clock in the browser timezone (tooltip / title). */
function formatTimeComponentAbsolute(ms) {
    try {
        return new Date(ms).toLocaleString(undefined, { timeZone: getBrowserTimeZone() });
    } catch (e) {
        return new Date(ms).toLocaleString();
    }
}

function updateTimeComponentElement(component, startTimeValue) {
    if (!component) return;
    if (startTimeValue !== undefined && startTimeValue !== null && startTimeValue !== '') {
        var next = String(startTimeValue);
        if (component.getAttribute('data-start-time') !== next) {
            component.setAttribute('data-start-time', next);
        }
    }
    var current = component.dataset.startTime;
    if (!current) return;
    var startTimeMs = parseTimeComponentStart(current);
    if (Number.isNaN(startTimeMs)) return;
    var formattedTime = formatTimeDiff(Date.now() - startTimeMs);
    if (component.textContent !== formattedTime) {
        component.textContent = formattedTime;
    }
    var absolute = formatTimeComponentAbsolute(startTimeMs);
    if (component.getAttribute('title') !== absolute) {
        component.setAttribute('title', absolute);
    }
}

function updateAllTimeComponents() {
    document.querySelectorAll('.time-component').forEach(function(component) {
        updateTimeComponentElement(component);
    });
}

/**
 * Apply changeProperty local timestamp to linked .time-component nodes.
 * Updates data-start-time from msg.changed without writing wall-clock into textContent.
 */
function applyTimeComponentsForProperty(propertyName, changedLocal) {
    if (!propertyName || changedLocal === undefined || changedLocal === null || changedLocal === '') {
        return;
    }
    var escaped = (window.CSS && CSS.escape) ? CSS.escape(propertyName) : String(propertyName).replace(/["\\]/g, '\\$&');
    var nodes = document.querySelectorAll(
        '.time-component[data-time-property="' + escaped + '"],' +
        '.time-component[id="time:' + escaped + '"],' +
        '.time-component[id="prop_changed:' + escaped + '"]'
    );
    nodes.forEach(function(el) {
        el.setAttribute('data-time-synced', '1');
        updateTimeComponentElement(el, changedLocal);
    });
}

/** Reveal async-loading wrapper (remove data-async-loading attribute). */
window.AsyncLoading = {
  reveal: function (el) {
    if (el) el.removeAttribute("data-async-loading");
  },
  revealClosest: function (node, selector) {
    var wrap = node && node.closest(selector || "[data-async-loading]");
    if (wrap) wrap.removeAttribute("data-async-loading");
    return wrap;
  },
};
