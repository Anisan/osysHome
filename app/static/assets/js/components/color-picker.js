(function() {
    if (window.__osysColorPickerVueStyles) return;
    window.__osysColorPickerVueStyles = true;

    var style = document.createElement('style');
    style.type = 'text/css';
    style.textContent = [
        '.color-picker-field .color-picker-group {',
        '  width: fit-content;',
        '  max-width: 100%;',
        '}',
        '.color-picker-field .color-picker-swatch {',
        '  position: relative;',
        '  width: 2.75rem;',
        '  min-width: 2.75rem;',
        '  height: auto;',
        '  padding: 0;',
        '  overflow: hidden;',
        '  background-color: transparent;',
        '  cursor: pointer;',
        '}',
        '.color-picker-field .color-picker-swatch.is-empty {',
        '  background-color: var(--bs-secondary-bg, #e9ecef);',
        '  background-image:',
        '    linear-gradient(45deg, rgba(0, 0, 0, 0.12) 25%, transparent 25%),',
        '    linear-gradient(-45deg, rgba(0, 0, 0, 0.12) 25%, transparent 25%),',
        '    linear-gradient(45deg, transparent 75%, rgba(0, 0, 0, 0.12) 75%),',
        '    linear-gradient(-45deg, transparent 75%, rgba(0, 0, 0, 0.12) 75%);',
        '  background-size: 10px 10px;',
        '  background-position: 0 0, 0 5px, 5px -5px, -5px 0;',
        '}',
        '.color-picker-field .color-picker-swatch.is-empty::after {',
        '  content: "";',
        '  position: absolute;',
        '  inset: 0;',
        '  background: linear-gradient(',
        '    to top right,',
        '    transparent calc(50% - 1px),',
        '    rgba(220, 53, 69, 0.85) calc(50% - 1px),',
        '    rgba(220, 53, 69, 0.85) calc(50% + 1px),',
        '    transparent calc(50% + 1px)',
        '  );',
        '  pointer-events: none;',
        '  z-index: 1;',
        '}',
        '.color-picker-field .color-picker-native {',
        '  position: absolute;',
        '  inset: 0;',
        '  width: 100%;',
        '  height: 100%;',
        '  margin: 0;',
        '  padding: 0;',
        '  border: 0;',
        '  opacity: 0;',
        '  cursor: pointer;',
        '  z-index: 2;',
        '}',
        '.color-picker-field .color-picker-status {',
        '  font-family: var(--bs-font-monospace, monospace);',
        '  font-size: 0.8125rem;',
        '  min-width: 5.5rem;',
        '  justify-content: center;',
        '  cursor: pointer;',
        '  user-select: none;',
        '}'
    ].join('\n');
    document.head.appendChild(style);
})();

Vue.component('color-picker', {
    delimiters: ['[[', ']]'],
    props: {
        value: { type: String, default: '' },
        inputId: { type: String, default: '' },
        name: { type: String, default: null },
        showClear: { type: Boolean, default: true },
        defaultColor: { type: String, default: '#000000' },
        label: { type: String, default: '' },
        notSetText: { type: String, default: 'Not set' },
        clearText: { type: String, default: 'Clear' },
        chooseText: { type: String, default: 'Choose color' },
        wrapperClass: { type: String, default: '' }
    },
    computed: {
        hasColor: function() {
            return !!(this.value && String(this.value).trim());
        },
        displayColor: function() {
            return this.hasColor ? String(this.value).trim() : this.defaultColor;
        },
        resolvedId: function() {
            if (this.inputId) return this.inputId;
            if (this._uid != null) return 'vue-color-picker-' + this._uid;
            return 'vue-color-picker';
        },
        fieldClass: function() {
            return ('color-picker-field ' + (this.wrapperClass || '')).trim();
        }
    },
    methods: {
        onNativeInput: function(event) {
            var next = event && event.target ? event.target.value : '';
            this.$emit('input', next || '');
            this.$emit('changed', next || '');
        },
        clearColor: function() {
            this.$emit('input', '');
            this.$emit('changed', '');
        },
        openPicker: function() {
            var input = this.$refs.nativeInput;
            if (!input) return;
            try {
                if (typeof input.showPicker === 'function') {
                    input.showPicker();
                    return;
                }
            } catch (e) { /* fallback ниже */ }
            input.click();
        },
        onStatusKeydown: function(event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                this.openPicker();
            }
        }
    },
    template: '\
<div :class="fieldClass" :data-color-picker-field="resolvedId">\
    <div class="input-group color-picker-group">\
        <div class="input-group-text color-picker-swatch"\
             :class="{ \'is-empty\': !hasColor }"\
             :style="hasColor ? { backgroundColor: displayColor } : null"\
             :title="chooseText">\
            <input type="color"\
                   class="color-picker-native"\
                   ref="nativeInput"\
                   :id="resolvedId"\
                   :name="name"\
                   :value="displayColor"\
                   :data-has-color="hasColor ? \'1\' : \'0\'"\
                   :data-default-color="defaultColor"\
                   :aria-label="label || chooseText"\
                   @input="onNativeInput">\
        </div>\
        <span class="input-group-text color-picker-status"\
              :class="{ \'text-muted\': !hasColor }"\
              :title="chooseText"\
              role="button"\
              tabindex="0"\
              @click="openPicker"\
              @keydown="onStatusKeydown">\
            [[ hasColor ? displayColor : notSetText ]]\
        </span>\
        <button v-if="showClear"\
                type="button"\
                class="btn btn-outline-secondary"\
                :title="clearText"\
                :aria-label="clearText"\
                :disabled="!hasColor"\
                @click="clearColor">\
            <i class="fas fa-times"></i>\
        </button>\
    </div>\
</div>'
});
