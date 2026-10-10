(function() {
    'use strict';

    var FIELD_DEFS = {
        second: { key: 'second', min: 0, max: 59 },
        minute: { key: 'minute', min: 0, max: 59 },
        hour: { key: 'hour', min: 0, max: 23 },
        day: { key: 'day', min: 1, max: 31 },
        month: { key: 'month', min: 1, max: 12, named: true },
        dow: { key: 'dow', min: 0, max: 6, named: true }
    };

    var ORDER_5 = ['minute', 'hour', 'day', 'month', 'dow'];
    // croniter: seconds are the 6th (last) field
    var ORDER_6 = ['minute', 'hour', 'day', 'month', 'dow', 'second'];

    var PRESETS_5 = {
        every_minute: '* * * * *',
        every_5_min: '*/5 * * * *',
        hourly: '0 * * * *',
        daily: '0 0 * * *',
        weekly: '0 0 * * 0',
        monthly: '0 0 1 * *'
    };

    var PRESETS_6 = {
        every_minute: '* * * * * 0',
        every_5_min: '*/5 * * * * 0',
        hourly: '0 * * * * 0',
        daily: '0 0 * * * 0',
        weekly: '0 0 * * 0 0',
        monthly: '0 0 1 * * 0'
    };

    var MONTH_ALIASES = {
        JAN: 1, FEB: 2, MAR: 3, APR: 4, MAY: 5, JUN: 6,
        JUL: 7, AUG: 8, SEP: 9, OCT: 10, NOV: 11, DEC: 12
    };

    var DOW_ALIASES = {
        SUN: 0, MON: 1, TUE: 2, WED: 3, THU: 4, FRI: 5, SAT: 6
    };

    var fields = new Map();
    var modals = new Map();

    function i18n(modalEl, key, fallback) {
        if (window.CronBuilderLocale && window.CronBuilderLocale[key]) {
            return window.CronBuilderLocale[key];
        }
        if (!modalEl) return fallback || key;
        var map = {
            every: 'i18nEvery',
            step: 'i18nStep',
            list: 'i18nList',
            range: 'i18nRange',
            custom: 'i18nCustom',
            second: 'i18nSecond',
            minute: 'i18nMinute',
            hour: 'i18nHour',
            day: 'i18nDay',
            month: 'i18nMonth',
            dow: 'i18nDow',
            hintEvery: 'i18nHintEvery',
            hintStep: 'i18nHintStep',
            hintList: 'i18nHintList',
            hintRange: 'i18nHintRange',
            hintCustom: 'i18nHintCustom',
            previewEmpty: 'i18nPreviewEmpty',
            dowNames: 'i18nDowNames',
            monthNames: 'i18nMonthNames',
            invalidExpr: 'i18nInvalidExpr',
            invalidField: 'i18nInvalidField',
            listRequired: 'i18nListRequired',
            rangeOrder: 'i18nRangeOrder',
            stepInvalid: 'i18nStepInvalid',
            nextRuns: 'i18nNextRuns',
            timezone: 'i18nTimezone',
            loadingNext: 'i18nLoadingNext'
        };
        var dsKey = map[key];
        var val = dsKey ? modalEl.dataset[dsKey] : '';
        return val || fallback || key;
    }

    function splitNames(modalEl, key) {
        var raw = key === 'dow'
            ? i18n(modalEl, 'dowNames', 'Sun,Mon,Tue,Wed,Thu,Fri,Sat')
            : i18n(modalEl, 'monthNames', 'Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec');
        return String(raw).split(',').map(function(s) { return s.trim(); }).filter(Boolean);
    }

    function namedChoices(modalEl, key) {
        var def = FIELD_DEFS[key];
        if (!def || !def.named) return null;
        var names = splitNames(modalEl, key);
        var choices = [];
        for (var n = def.min; n <= def.max; n++) {
            var label = names[key === 'month' ? n - 1 : n] || String(n);
            choices.push({ value: n, label: label + ' (' + n + ')' });
        }
        return choices;
    }

    function clampInt(value, min, max, fallback) {
        var n = parseInt(value, 10);
        if (isNaN(n)) return fallback;
        if (n < min) return min;
        if (n > max) return max;
        return n;
    }

    function detectFormat(parts) {
        if (parts.length === 6) return 6;
        return 5;
    }

    function defaultFields(format) {
        var order = format === 6 ? ORDER_6 : ORDER_5;
        var out = {};
        order.forEach(function(key) {
            out[key] = '*';
        });
        return out;
    }

    function parseCron(str) {
        var text = String(str || '').trim().replace(/\s+/g, ' ');
        if (!text) {
            return { format: 5, fields: defaultFields(5) };
        }
        var parts = text.split(' ');
        if (parts.length !== 5 && parts.length !== 6) {
            return { format: 5, fields: defaultFields(5), invalid: true, raw: text };
        }
        var format = detectFormat(parts);
        var order = format === 6 ? ORDER_6 : ORDER_5;
        var out = {};
        order.forEach(function(key, idx) {
            out[key] = parts[idx];
        });
        return { format: format, fields: out };
    }

    function buildCron(fieldMap, format) {
        var order = format === 6 ? ORDER_6 : ORDER_5;
        return order.map(function(key) {
            var v = fieldMap[key];
            return (v === undefined || v === null || v === '') ? '*' : String(v).trim();
        }).join(' ');
    }

    function resolveTokenNumber(token, key) {
        var t = String(token || '').trim();
        if (/^\d+$/.test(t)) return parseInt(t, 10);
        var upper = t.toUpperCase();
        if (key === 'month' && Object.prototype.hasOwnProperty.call(MONTH_ALIASES, upper)) {
            return MONTH_ALIASES[upper];
        }
        if (key === 'dow' && Object.prototype.hasOwnProperty.call(DOW_ALIASES, upper)) {
            return DOW_ALIASES[upper];
        }
        // croniter often accepts 7 as Sunday
        if (key === 'dow' && t === '7') return 0;
        return NaN;
    }

    function classifyField(value) {
        var v = String(value || '').trim();
        if (!v || v === '*') {
            return { mode: 'every', value: '*', step: 1, list: '', from: '', to: '', custom: '*' };
        }
        var stepMatch = v.match(/^\*\/(\d+)$/);
        if (stepMatch) {
            return { mode: 'step', value: v, step: parseInt(stepMatch[1], 10) || 1, list: '', from: '', to: '', custom: v };
        }
        var rangeMatch = v.match(/^([A-Za-z]+|\d+)-([A-Za-z]+|\d+)$/);
        if (rangeMatch) {
            return {
                mode: 'range',
                value: v,
                step: 1,
                list: '',
                from: rangeMatch[1],
                to: rangeMatch[2],
                custom: v
            };
        }
        if (v.indexOf(',') !== -1) {
            var parts = v.split(',');
            var allSimple = parts.every(function(p) {
                return /^([A-Za-z]+|\d+)$/.test(p.trim());
            });
            if (allSimple) {
                return { mode: 'list', value: v, step: 1, list: v, from: '', to: '', custom: v };
            }
        }
        if (/^([A-Za-z]+|\d+)$/.test(v)) {
            return { mode: 'list', value: v, step: 1, list: v, from: '', to: '', custom: v };
        }
        return { mode: 'custom', value: v, step: 1, list: '', from: '', to: '', custom: v };
    }

    function validateFieldPart(part, key, def) {
        var p = String(part || '').trim();
        if (!p) return false;
        if (p === '*') return true;

        var stepOnly = p.match(/^\*\/(\d+)$/);
        if (stepOnly) {
            var step = parseInt(stepOnly[1], 10);
            return step >= 1;
        }

        var full = p.match(/^([A-Za-z]+|\d+)(?:-([A-Za-z]+|\d+))?(?:\/(\d+))?$/);
        if (!full) return false;

        var from = resolveTokenNumber(full[1], key);
        if (isNaN(from) || from < def.min || from > def.max) return false;

        if (full[2] !== undefined) {
            var to = resolveTokenNumber(full[2], key);
            if (isNaN(to) || to < def.min || to > def.max) return false;
        }

        if (full[3] !== undefined) {
            var s = parseInt(full[3], 10);
            if (isNaN(s) || s < 1) return false;
        }
        return true;
    }

    function validateFieldValue(key, value) {
        var def = FIELD_DEFS[key];
        var v = String(value || '').trim();
        if (!v) return false;
        var parts = v.split(',');
        for (var i = 0; i < parts.length; i++) {
            if (!validateFieldPart(parts[i], key, def)) return false;
        }
        return true;
    }

    function getListValue(editor) {
        if (editor.listCheckboxes && editor.listCheckboxes.length) {
            var vals = [];
            editor.listCheckboxes.forEach(function(cb) {
                if (cb.checked) vals.push(cb.value);
            });
            return vals.join(',');
        }
        return editor.listInput ? editor.listInput.value : '';
    }

    function setListValue(editor, listStr) {
        var raw = String(listStr || '').trim();
        var tokens = raw ? raw.split(',').map(function(s) { return s.trim(); }).filter(Boolean) : [];
        if (editor.listCheckboxes && editor.listCheckboxes.length) {
            var selected = {};
            tokens.forEach(function(tok) {
                var n = resolveTokenNumber(tok, editor.key);
                if (!isNaN(n)) selected[String(n)] = true;
                // dow: 7 == 0
                if (editor.key === 'dow' && (tok === '7' || n === 7)) selected['0'] = true;
            });
            editor.listCheckboxes.forEach(function(cb) {
                cb.checked = !!selected[cb.value];
            });
            return;
        }
        if (editor.listInput) editor.listInput.value = raw;
    }

    function getRangeValue(editor, which) {
        var el = which === 'from' ? editor.fromInput : editor.toInput;
        return el ? el.value : '';
    }

    function setRangeValue(editor, from, to, key) {
        var fromNum = resolveTokenNumber(from, key);
        var toNum = resolveTokenNumber(to, key);
        if (editor.fromInput) {
            editor.fromInput.value = isNaN(fromNum) ? String(editor.def.min) : String(fromNum);
        }
        if (editor.toInput) {
            editor.toInput.value = isNaN(toNum) ? String(editor.def.max) : String(toNum);
        }
    }

    function valueFromEditor(editor) {
        var mode = editor.modeSelect.value;
        var def = editor.def;
        if (mode === 'every') return '*';
        if (mode === 'step') {
            var step = clampInt(editor.stepInput.value, 1, Math.max(1, def.max), 1);
            return '*/' + step;
        }
        if (mode === 'list') {
            var list = String(getListValue(editor) || '').trim();
            if (!list) return '';
            return list.replace(/\s+/g, '');
        }
        if (mode === 'range') {
            var from = clampInt(getRangeValue(editor, 'from'), def.min, def.max, def.min);
            var to = clampInt(getRangeValue(editor, 'to'), def.min, def.max, def.max);
            return from + '-' + to;
        }
        var custom = String(editor.customInput.value || '').trim();
        return custom || '*';
    }

    function formatNamedToken(modalEl, key, num) {
        var names = splitNames(modalEl, key);
        var label = key === 'month' ? names[num - 1] : names[num];
        return label || String(num);
    }

    function formatHintPart(modalEl, key, fieldValue) {
        var classified = classifyField(fieldValue);
        var label = i18n(modalEl, key, key);
        var text;
        var def = FIELD_DEFS[key];
        if (classified.mode === 'every') {
            text = i18n(modalEl, 'hintEvery', 'Every value');
        } else if (classified.mode === 'step') {
            text = i18n(modalEl, 'hintStep', 'Every {n}').replace('{n}', classified.step);
        } else if (classified.mode === 'list') {
            var listText = classified.list || classified.value;
            if (def.named) {
                listText = String(listText).split(',').map(function(tok) {
                    var n = resolveTokenNumber(tok.trim(), key);
                    return isNaN(n) ? tok.trim() : formatNamedToken(modalEl, key, n);
                }).join(', ');
            }
            text = i18n(modalEl, 'hintList', 'At {values}').replace('{values}', listText);
        } else if (classified.mode === 'range') {
            var fromLabel = classified.from;
            var toLabel = classified.to;
            if (def.named) {
                var fromN = resolveTokenNumber(classified.from, key);
                var toN = resolveTokenNumber(classified.to, key);
                if (!isNaN(fromN)) fromLabel = formatNamedToken(modalEl, key, fromN);
                if (!isNaN(toN)) toLabel = formatNamedToken(modalEl, key, toN);
            }
            text = i18n(modalEl, 'hintRange', 'From {from} to {to}')
                .replace('{from}', fromLabel)
                .replace('{to}', toLabel);
        } else {
            text = i18n(modalEl, 'hintCustom', 'Custom: {value}').replace('{value}', classified.custom);
        }
        return label + ': ' + text;
    }

    function humanHint(modalEl, fieldMap, format) {
        var order = format === 6 ? ORDER_6 : ORDER_5;
        return order.map(function(key) {
            return formatHintPart(modalEl, key, fieldMap[key]);
        }).join(' · ');
    }

    function validateCollected(modalState, collected) {
        var errors = [];
        var order = collected.format === 6 ? ORDER_6 : ORDER_5;
        order.forEach(function(key) {
            var editor = modalState.editors[key];
            var value = collected.fields[key];
            var fieldLabel = i18n(modalState.element, key, key);
            if (editor && editor.modeSelect.value === 'list' && !String(value || '').trim()) {
                errors.push(
                    i18n(modalState.element, 'listRequired', 'Select at least one value for {field}')
                        .replace('{field}', fieldLabel)
                );
                if (editor.row) editor.row.classList.add('has-error');
                return;
            }
            if (editor && editor.modeSelect.value === 'range') {
                var from = clampInt(getRangeValue(editor, 'from'), editor.def.min, editor.def.max, editor.def.min);
                var to = clampInt(getRangeValue(editor, 'to'), editor.def.min, editor.def.max, editor.def.max);
                if (from > to) {
                    errors.push(
                        i18n(modalState.element, 'rangeOrder', 'Range start must be less than or equal to end ({field})')
                            .replace('{field}', fieldLabel)
                    );
                    if (editor.row) editor.row.classList.add('has-error');
                    return;
                }
            }
            if (editor && editor.modeSelect.value === 'step') {
                var step = parseInt(editor.stepInput.value, 10);
                if (isNaN(step) || step < 1) {
                    errors.push(
                        i18n(modalState.element, 'stepInvalid', 'Step must be a positive integer ({field})')
                            .replace('{field}', fieldLabel)
                    );
                    if (editor.row) editor.row.classList.add('has-error');
                    return;
                }
            }
            if (!validateFieldValue(key, value)) {
                errors.push(
                    i18n(modalState.element, 'invalidField', 'Invalid value for {field}: {value}')
                        .replace('{field}', fieldLabel)
                        .replace('{value}', value || '')
                );
                if (editor && editor.row) editor.row.classList.add('has-error');
            } else if (editor && editor.row) {
                editor.row.classList.remove('has-error');
            }
        });
        return errors;
    }

    function getField(inputId) {
        var field = fields.get(inputId);
        if (!field) return null;
        field.input = document.getElementById(inputId);
        return field;
    }

    function notifyChange(inputId) {
        var field = getField(inputId);
        if (!field || !field.input) return;
        if (typeof field.onChange === 'function') {
            field.onChange(field.input.value, field.input);
        }
        field.input.dispatchEvent(new Event('input', { bubbles: true }));
        field.input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function setValue(inputId, value, options) {
        var field = getField(inputId);
        if (!field || !field.input) return;
        var opts = options || {};
        field.input.value = String(value || '').trim();
        notifyChange(inputId);
        if (opts.closeModal) {
            var modalState = modals.get(field.modalId);
            if (modalState && modalState.element && window.bootstrap) {
                var modalInstance = bootstrap.Modal.getInstance(modalState.element)
                    || bootstrap.Modal.getOrCreateInstance(modalState.element);
                modalInstance.hide();
            }
        }
    }

    function modeOptionsHtml(modalEl) {
        return [
            ['every', i18n(modalEl, 'every', 'Every')],
            ['step', i18n(modalEl, 'step', 'Every N')],
            ['list', i18n(modalEl, 'list', 'List')],
            ['range', i18n(modalEl, 'range', 'Range')],
            ['custom', i18n(modalEl, 'custom', 'Custom')]
        ].map(function(pair) {
            return '<option value="' + pair[0] + '">' + pair[1] + '</option>';
        }).join('');
    }

    function buildSelectOptions(choices, selected) {
        return choices.map(function(c) {
            var sel = String(c.value) === String(selected) ? ' selected' : '';
            return '<option value="' + c.value + '"' + sel + '>' + c.label + '</option>';
        }).join('');
    }

    function buildCheckboxGrid(modalState, key, choices) {
        var wrap = document.createElement('div');
        wrap.className = 'cron-check-grid';
        var boxes = [];
        choices.forEach(function(c) {
            var id = modalState.id + '-' + key + '-cb-' + c.value;
            var item = document.createElement('div');
            item.className = 'form-check';
            item.innerHTML =
                '<input class="form-check-input" type="checkbox" value="' + c.value + '" id="' + id + '">' +
                '<label class="form-check-label small" for="' + id + '">' + c.label + '</label>';
            wrap.appendChild(item);
            boxes.push(item.querySelector('input'));
        });
        return { wrap: wrap, boxes: boxes };
    }

    function buildFieldRows(modalState) {
        var container = modalState.fieldsEl;
        if (!container) return;
        container.innerHTML = '';
        modalState.editors = {};

        ORDER_6.forEach(function(key) {
            var def = FIELD_DEFS[key];
            var choices = namedChoices(modalState.element, key);
            var row = document.createElement('div');
            row.className = 'cron-builder-field-row';
            row.dataset.fieldKey = key;

            var labelCol = document.createElement('div');
            var label = document.createElement('label');
            label.className = 'form-label small mb-1';
            label.textContent = i18n(modalState.element, key, key);
            labelCol.appendChild(label);

            var modeCol = document.createElement('div');
            var modeSelect = document.createElement('select');
            modeSelect.className = 'form-select form-select-sm';
            modeSelect.innerHTML = modeOptionsHtml(modalState.element);
            modeCol.appendChild(modeSelect);

            var extras = document.createElement('div');
            extras.className = 'cron-builder-extras';

            var stepWrap = document.createElement('div');
            stepWrap.className = 'cron-extra cron-extra-step';
            stepWrap.innerHTML = '<input type="number" class="form-control form-control-sm" min="1" step="1" value="5">';

            var listWrap = document.createElement('div');
            listWrap.className = 'cron-extra cron-extra-list';
            var listCheckboxes = null;
            var listInput = null;
            if (choices) {
                var grid = buildCheckboxGrid(modalState, key, choices);
                listWrap.appendChild(grid.wrap);
                listCheckboxes = grid.boxes;
            } else {
                listWrap.innerHTML = '<input type="text" class="form-control form-control-sm" placeholder="0,15,30" autocomplete="off" spellcheck="false">';
                listInput = listWrap.querySelector('input');
            }

            var rangeWrap = document.createElement('div');
            rangeWrap.className = 'cron-extra cron-extra-range';
            var fromInput;
            var toInput;
            if (choices) {
                rangeWrap.innerHTML =
                    '<div class="input-group input-group-sm">' +
                    '<select class="form-select cron-range-from">' + buildSelectOptions(choices, def.min) + '</select>' +
                    '<span class="input-group-text">–</span>' +
                    '<select class="form-select cron-range-to">' + buildSelectOptions(choices, def.max) + '</select>' +
                    '</div>';
            } else {
                rangeWrap.innerHTML =
                    '<div class="input-group input-group-sm">' +
                    '<input type="number" class="form-control cron-range-from" min="' + def.min + '" max="' + def.max + '" value="' + def.min + '">' +
                    '<span class="input-group-text">–</span>' +
                    '<input type="number" class="form-control cron-range-to" min="' + def.min + '" max="' + def.max + '" value="' + def.max + '">' +
                    '</div>';
            }
            fromInput = rangeWrap.querySelector('.cron-range-from');
            toInput = rangeWrap.querySelector('.cron-range-to');

            var customWrap = document.createElement('div');
            customWrap.className = 'cron-extra cron-extra-custom';
            customWrap.innerHTML = '<input type="text" class="form-control form-control-sm" placeholder="*" autocomplete="off" spellcheck="false">';

            extras.appendChild(stepWrap);
            extras.appendChild(listWrap);
            extras.appendChild(rangeWrap);
            extras.appendChild(customWrap);

            row.appendChild(labelCol);
            row.appendChild(modeCol);
            row.appendChild(extras);
            container.appendChild(row);

            var editor = {
                key: key,
                def: def,
                row: row,
                modeSelect: modeSelect,
                stepInput: stepWrap.querySelector('input'),
                listInput: listInput,
                listCheckboxes: listCheckboxes,
                fromInput: fromInput,
                toInput: toInput,
                customInput: customWrap.querySelector('input'),
                wraps: {
                    every: null,
                    step: stepWrap,
                    list: listWrap,
                    range: rangeWrap,
                    custom: customWrap
                }
            };

            function onEditorChange() {
                syncExtrasVisibility(editor);
                updatePreview(modalState);
            }

            modeSelect.addEventListener('change', onEditorChange);
            var listenEls = [editor.stepInput, editor.fromInput, editor.toInput, editor.customInput];
            if (editor.listInput) listenEls.push(editor.listInput);
            listenEls.forEach(function(el) {
                if (!el) return;
                el.addEventListener('input', onEditorChange);
                el.addEventListener('change', onEditorChange);
            });
            if (editor.listCheckboxes) {
                editor.listCheckboxes.forEach(function(cb) {
                    cb.addEventListener('change', onEditorChange);
                });
            }

            modalState.editors[key] = editor;
            syncExtrasVisibility(editor);
        });
    }

    function syncExtrasVisibility(editor) {
        var mode = editor.modeSelect.value;
        Object.keys(editor.wraps).forEach(function(m) {
            var wrap = editor.wraps[m];
            if (!wrap) return;
            wrap.classList.toggle('d-none', m !== mode);
        });
    }

    function setFormatUI(modalState, format) {
        var f5 = modalState.format5;
        var f6 = modalState.format6;
        if (f5) f5.checked = format !== 6;
        if (f6) f6.checked = format === 6;
        Object.keys(modalState.editors || {}).forEach(function(key) {
            var editor = modalState.editors[key];
            var show = format === 6 || key !== 'second';
            editor.row.classList.toggle('is-hidden', !show);
        });
    }

    function getFormat(modalState) {
        if (modalState.format6 && modalState.format6.checked) return 6;
        return 5;
    }

    function applyParsedToEditors(modalState, parsed) {
        modalState._applying = true;
        try {
            setFormatUI(modalState, parsed.format);
            ORDER_6.forEach(function(key) {
                var editor = modalState.editors[key];
                if (!editor) return;
                var raw = parsed.fields[key];
                if (raw === undefined) raw = (key === 'second') ? '0' : '*';
                var classified = classifyField(raw);
                editor.modeSelect.value = classified.mode;
                editor.stepInput.value = String(classified.step || 1);
                setListValue(editor, classified.list || (classified.mode === 'list' ? classified.value : ''));
                setRangeValue(
                    editor,
                    classified.from !== '' ? classified.from : editor.def.min,
                    classified.to !== '' ? classified.to : editor.def.max,
                    key
                );
                editor.customInput.value = classified.custom || raw;
                editor.row.classList.remove('has-error');
                syncExtrasVisibility(editor);
            });
            updatePreview(modalState);
        } finally {
            modalState._applying = false;
        }
    }

    function loadFromActiveInput(modalState) {
        var inputId = modalState.activeInputId;
        if (!inputId) {
            var openBtn = document.querySelector('[data-cron-builder-open][data-bs-target="#' + modalState.id + '"]');
            if (openBtn) {
                inputId = openBtn.getAttribute('data-cron-builder-open');
                modalState.activeInputId = inputId;
                if (inputId && !fields.has(inputId)) {
                    register(inputId, { modalId: modalState.id });
                }
            }
        }
        var field = getField(modalState.activeInputId);
        var input = field && field.input ? field.input : (modalState.activeInputId
            ? document.getElementById(modalState.activeInputId)
            : null);
        var raw = input ? input.value : '';
        var parsed = parseCron(raw);
        applyParsedToEditors(modalState, parsed);
        if (parsed.invalid) {
            setValidationUI(modalState, [
                i18n(modalState.element, 'invalidExpr', 'Invalid cron expression')
            ]);
        }
        return parsed;
    }

    function resolveOpenTrigger(event) {
        var t = event && event.relatedTarget;
        if (!t) return null;
        if (t.getAttribute && t.getAttribute('data-cron-builder-open')) return t;
        if (t.closest) return t.closest('[data-cron-builder-open]');
        return null;
    }

    function preventParentHide(event) {
        event.preventDefault();
    }

    function attachNestedModalGuards(modalState) {
        detachNestedModalGuards(modalState);
        var parents = [];
        document.querySelectorAll('.modal.show').forEach(function(el) {
            if (el === modalState.element) return;
            parents.push(el);
            el.addEventListener('hide.bs.modal', preventParentHide);
        });
        modalState._parentModals = parents;
        if (!parents.length) return;

        // Stack cron builder above parent modal + backdrop
        modalState.element.style.zIndex = '1065';
        setTimeout(function() {
            var backdrops = document.querySelectorAll('.modal-backdrop');
            if (backdrops.length) {
                var last = backdrops[backdrops.length - 1];
                last.style.zIndex = '1060';
                last.classList.add('cron-builder-backdrop');
            }
        }, 0);
    }

    function detachNestedModalGuards(modalState) {
        (modalState._parentModals || []).forEach(function(el) {
            el.removeEventListener('hide.bs.modal', preventParentHide);
        });
        modalState._parentModals = [];
        if (modalState.element) {
            modalState.element.style.zIndex = '';
        }
        document.querySelectorAll('.modal-backdrop.cron-builder-backdrop').forEach(function(bd) {
            bd.classList.remove('cron-builder-backdrop');
            bd.style.zIndex = '';
        });
        // Keep body in modal mode if a parent modal is still open
        if (document.querySelector('.modal.show')) {
            document.body.classList.add('modal-open');
        }
    }

    function collectFields(modalState) {
        var format = getFormat(modalState);
        var out = {};
        var order = format === 6 ? ORDER_6 : ORDER_5;
        order.forEach(function(key) {
            out[key] = valueFromEditor(modalState.editors[key]);
        });
        return { format: format, fields: out };
    }

    function setValidationUI(modalState, errors) {
        var previewBox = modalState.previewExpr
            ? modalState.previewExpr.closest('.cron-builder-preview')
            : null;
        if (modalState.previewError) {
            if (errors.length) {
                modalState.previewError.textContent = errors[0];
                modalState.previewError.classList.remove('d-none');
            } else {
                modalState.previewError.textContent = '';
                modalState.previewError.classList.add('d-none');
            }
        }
        if (previewBox) {
            previewBox.classList.toggle('is-invalid', errors.length > 0);
        }
        if (modalState.applyBtn) {
            modalState.applyBtn.disabled = errors.length > 0;
        }
    }

    function clearNextRuns(modalState) {
        if (modalState.nextRunsWrap) {
            modalState.nextRunsWrap.classList.add('d-none');
        }
        if (modalState.nextRunsList) {
            modalState.nextRunsList.innerHTML = '';
        }
        if (modalState.nextRunsTz) {
            modalState.nextRunsTz.textContent = '';
        }
    }

    function renderNextRuns(modalState, nextRuns, timezone) {
        if (!modalState.nextRunsWrap || !modalState.nextRunsList) return;
        var runs = Array.isArray(nextRuns) ? nextRuns : [];
        if (!runs.length) {
            clearNextRuns(modalState);
            return;
        }
        modalState.nextRunsWrap.classList.remove('d-none');
        if (modalState.nextRunsLabel) {
            modalState.nextRunsLabel.textContent = i18n(modalState.element, 'nextRuns', 'Next runs');
        }
        modalState.nextRunsList.innerHTML = '';
        runs.forEach(function(item) {
            var li = document.createElement('li');
            li.textContent = item;
            modalState.nextRunsList.appendChild(li);
        });
        if (modalState.nextRunsTz) {
            modalState.nextRunsTz.textContent = timezone
                ? i18n(modalState.element, 'timezone', 'Timezone: {tz}').replace('{tz}', timezone)
                : '';
        }
    }

    function scheduleNextRunsFetch(modalState, expr, hasErrors) {
        if (modalState._nextRunsTimer) {
            clearTimeout(modalState._nextRunsTimer);
            modalState._nextRunsTimer = null;
        }
        if (!modalState._open) {
            clearNextRuns(modalState);
            return;
        }
        if (hasErrors || !expr || expr.indexOf('?') !== -1) {
            clearNextRuns(modalState);
            return;
        }
        if (modalState.nextRunsWrap && modalState.nextRunsList) {
            modalState.nextRunsWrap.classList.remove('d-none');
            if (modalState.nextRunsLabel) {
                modalState.nextRunsLabel.textContent = i18n(modalState.element, 'nextRuns', 'Next runs');
            }
            modalState.nextRunsList.innerHTML = '';
            var loading = document.createElement('li');
            loading.className = 'text-muted';
            loading.textContent = i18n(modalState.element, 'loadingNext', 'Loading next runs...');
            modalState.nextRunsList.appendChild(loading);
            if (modalState.nextRunsTz) modalState.nextRunsTz.textContent = '';
        }
        var requestId = (modalState._nextRunsRequestId || 0) + 1;
        modalState._nextRunsRequestId = requestId;
        modalState._nextRunsTimer = setTimeout(function() {
            fetch('/api/utils/cron/validate', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ crontab: expr, count: 5 })
            })
                .then(function(response) {
                    if (!response.ok) throw new Error('HTTP ' + response.status);
                    return response.json();
                })
                .then(function(data) {
                    if (requestId !== modalState._nextRunsRequestId) return;
                    if (data && data.ok && Array.isArray(data.next_runs) && data.next_runs.length) {
                        renderNextRuns(modalState, data.next_runs, data.timezone);
                    } else {
                        clearNextRuns(modalState);
                        if (data && data.ok === false && data.errors && data.errors.length) {
                            var msg = data.errors[0].message || i18n(modalState.element, 'invalidExpr', 'Invalid cron expression');
                            setValidationUI(modalState, [msg]);
                        }
                    }
                })
                .catch(function() {
                    if (requestId !== modalState._nextRunsRequestId) return;
                    clearNextRuns(modalState);
                });
        }, 400);
    }

    function updatePreview(modalState) {
        var collected = collectFields(modalState);
        var expr = buildCron(collected.fields, collected.format);
        // empty list fields leave blank tokens — rebuild carefully
        var order = collected.format === 6 ? ORDER_6 : ORDER_5;
        var hasEmpty = order.some(function(key) {
            return collected.fields[key] === '';
        });
        if (!hasEmpty && modalState.previewExpr) {
            modalState.previewExpr.textContent = expr;
        } else if (modalState.previewExpr) {
            modalState.previewExpr.textContent = order.map(function(key) {
                return collected.fields[key] === '' ? '?' : collected.fields[key];
            }).join(' ');
        }
        if (modalState.previewHint) {
            var hintMap = {};
            order.forEach(function(key) {
                hintMap[key] = collected.fields[key] || '*';
            });
            modalState.previewHint.textContent = humanHint(modalState.element, hintMap, collected.format);
        }
        var errors = validateCollected(modalState, collected);
        setValidationUI(modalState, errors);
        scheduleNextRunsFetch(modalState, hasEmpty ? '' : expr, errors.length > 0);
        return { expr: expr, errors: errors, collected: collected };
    }

    function applyPreset(modalState, presetKey) {
        var format = getFormat(modalState);
        var map = format === 6 ? PRESETS_6 : PRESETS_5;
        var expr = map[presetKey];
        if (!expr) return;
        applyParsedToEditors(modalState, parseCron(expr));
    }

    function bindModal(modalId) {
        if (modals.has(modalId)) return modals.get(modalId);
        var element = document.getElementById(modalId);
        if (!element) return null;

        var modalState = {
            id: modalId,
            element: element,
            fieldsEl: document.getElementById(modalId + '-fields'),
            format5: document.getElementById(modalId + '-format-5'),
            format6: document.getElementById(modalId + '-format-6'),
            previewExpr: document.getElementById(modalId + '-preview-expr'),
            previewHint: document.getElementById(modalId + '-preview-hint'),
            previewError: document.getElementById(modalId + '-preview-error'),
            nextRunsWrap: document.getElementById(modalId + '-next-runs'),
            nextRunsLabel: document.getElementById(modalId + '-next-runs-label'),
            nextRunsList: document.getElementById(modalId + '-next-runs-list'),
            nextRunsTz: document.getElementById(modalId + '-next-runs-tz'),
            applyBtn: document.getElementById(modalId + '-apply-btn'),
            presetsEl: document.getElementById(modalId + '-presets'),
            activeInputId: null,
            editors: {},
            _open: false,
            _nextRunsTimer: null,
            _nextRunsRequestId: 0
        };

        buildFieldRows(modalState);
        setFormatUI(modalState, 5);
        updatePreview(modalState);

        function onFormatChange() {
            if (modalState._applying) return;
            var format = getFormat(modalState);
            setFormatUI(modalState, format);
            var collected = collectFields(modalState);
            if (format === 6) {
                var secondEditor = modalState.editors.second;
                if (secondEditor && secondEditor.modeSelect.value === 'every') {
                    collected.fields.second = '0';
                }
            }
            applyParsedToEditors(modalState, collected);
        }

        if (modalState.format5) modalState.format5.addEventListener('change', onFormatChange);
        if (modalState.format6) modalState.format6.addEventListener('change', onFormatChange);

        if (modalState.presetsEl) {
            modalState.presetsEl.querySelectorAll('[data-cron-preset]').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    applyPreset(modalState, btn.getAttribute('data-cron-preset'));
                });
            });
        }

        if (modalState.applyBtn) {
            modalState.applyBtn.addEventListener('click', function() {
                if (!modalState.activeInputId) return;
                var result = updatePreview(modalState);
                if (result.errors.length) return;
                setValue(modalState.activeInputId, result.expr, { closeModal: true });
            });
        }

        element.addEventListener('show.bs.modal', function(event) {
            modalState._open = true;
            attachNestedModalGuards(modalState);
            var trigger = resolveOpenTrigger(event);
            if (trigger) {
                var inputId = trigger.getAttribute('data-cron-builder-open');
                if (inputId) {
                    modalState.activeInputId = inputId;
                    if (!fields.has(inputId)) {
                        register(inputId, { modalId: modalId });
                    }
                }
            }
            loadFromActiveInput(modalState);
        });

        element.addEventListener('shown.bs.modal', function() {
            attachNestedModalGuards(modalState);
            loadFromActiveInput(modalState);
        });

        element.addEventListener('hidden.bs.modal', function() {
            modalState._open = false;
            if (modalState._nextRunsTimer) {
                clearTimeout(modalState._nextRunsTimer);
                modalState._nextRunsTimer = null;
            }
            clearNextRuns(modalState);
            detachNestedModalGuards(modalState);
        });

        modals.set(modalId, modalState);
        return modalState;
    }

    function register(inputId, options) {
        var opts = options || {};
        if (fields.has(inputId)) {
            var existing = fields.get(inputId);
            if (opts.modalId) existing.modalId = opts.modalId;
            if (Object.prototype.hasOwnProperty.call(opts, 'onChange')) {
                existing.onChange = opts.onChange || null;
            }
            return {
                setValue: function(value, closeModal) {
                    setValue(inputId, value, { closeModal: !!closeModal });
                },
                getValue: function() {
                    var field = getField(inputId);
                    return field && field.input ? field.input.value : '';
                }
            };
        }

        var modalId = opts.modalId || 'cronBuilderModal';
        fields.set(inputId, {
            inputId: inputId,
            modalId: modalId,
            onChange: opts.onChange || null,
            input: null
        });
        bindModal(modalId);

        return {
            setValue: function(value, closeModal) {
                setValue(inputId, value, { closeModal: !!closeModal });
            },
            getValue: function() {
                var field = getField(inputId);
                return field && field.input ? field.input.value : '';
            }
        };
    }

    function openFromButton(btn, options) {
        if (!btn) return null;
        var opts = options || {};
        var inputId = btn.getAttribute('data-cron-builder-open');
        var target = btn.getAttribute('data-bs-target') || '';
        if (!inputId || target.indexOf('#') !== 0) return null;
        var modalId = target.slice(1);
        var modalState = bindModal(modalId);
        if (!modalState) return null;
        modalState.activeInputId = inputId;
        if (!fields.has(inputId)) {
            register(inputId, { modalId: modalId });
        }
        if (opts.show && window.bootstrap && modalState.element) {
            var instance = bootstrap.Modal.getOrCreateInstance(modalState.element);
            instance.show(btn);
        }
        return modalState;
    }

    function onOpenButtonClick(event) {
        var btn = event.target && event.target.closest
            ? event.target.closest('[data-cron-builder-open]')
            : null;
        if (!btn) return;
        // Only bind active input here. Do NOT stopPropagation — Bootstrap
        // data-bs-toggle on regular pages listens on document bubble.
        openFromButton(btn, { show: false });
    }

    function init() {
        if (!document.documentElement.dataset.cronBuilderClickBound) {
            document.addEventListener('click', onOpenButtonClick, true);
            document.documentElement.dataset.cronBuilderClickBound = '1';
        }
        document.querySelectorAll('[data-cron-builder-modal]').forEach(function(el) {
            bindModal(el.id);
        });
        document.querySelectorAll('[data-cron-builder-field]').forEach(function(el) {
            var inputId = el.getAttribute('data-cron-builder-field');
            if (!inputId) return;
            var modalId = 'cronBuilderModal';
            var openBtn = el.querySelector('[data-cron-builder-open]');
            if (openBtn) {
                var target = openBtn.getAttribute('data-bs-target') || '';
                if (target.indexOf('#') === 0 && target.length > 1) {
                    modalId = target.slice(1);
                }
            }
            register(inputId, { modalId: modalId });
        });
    }

    window.CronBuilder = {
        register: register,
        setValue: setValue,
        parseCron: parseCron,
        buildCron: buildCron,
        validateFieldValue: validateFieldValue,
        openFromButton: openFromButton,
        init: init
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
