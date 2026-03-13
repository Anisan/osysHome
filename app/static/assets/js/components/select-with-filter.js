Vue.component('select-with-filter', {
    delimiters: ['[[', ']]'],
    props: ['options', 'value', 'placeholder'],
    data() {
        return {
            search: '',
            isOpen: false,
            selectedKey: null,
            initialSet: true,
            dropTop: 0,
            dropLeft: 0,
            dropWidth: 0
        };
    },
    watch: {
        value(newVal) {
            this.selectedKey = newVal;
        },
        selectedKey(newVal) {
            if (!this.initialSet) {
                this.$emit('changed', newVal);
            }
            this.$emit('input', newVal);
            this.initialSet = false;
        }
    },
    computed: {
        filteredOptions() {
            if (!this.options) return [];
            var s = this.search.toLowerCase();
            return Object.keys(this.options).filter(function(key) {
                return (key + (this.options[key] || '')).toLowerCase().indexOf(s) !== -1;
            }.bind(this));
        },
        selectedDescription() {
            if (this.selectedKey && this.options && this.selectedKey in this.options) {
                return this.selectedKey + ' - ' + this.options[this.selectedKey];
            }
            return this.placeholder || 'Select...';
        }
    },
    methods: {
        openDropdown() {
            var rect = this.$refs.trigger.getBoundingClientRect();
            this.dropTop = rect.bottom;
            this.dropLeft = rect.left;
            this.dropWidth = rect.width;
            this.isOpen = true;
            this.$nextTick(function() {
                if (this.$refs.searchInput) this.$refs.searchInput.focus();
            });
        },
        selectOption(key) {
            this.selectedKey = key;
            this.isOpen = false;
            this.search = '';
        },
        clearSelection() {
            this.selectedKey = null;
            this.search = '';
        },
        handleClickOutside(event) {
            if (!this.$el.contains(event.target)) {
                this.isOpen = false;
            }
        }
    },
    mounted() {
        document.addEventListener('click', this.handleClickOutside);
        this.selectedKey = this.value;
    },
    beforeDestroy() {
        document.removeEventListener('click', this.handleClickOutside);
    },
    template: '\
<div style="position:relative; min-width:160px;">\
    <div class="input-group" ref="trigger">\
        <div class="form-control d-flex align-items-center" \
             style="cursor:pointer; background:var(--bs-body-bg);" \
             @click.stop="openDropdown()">\
            <span class="text-truncate flex-grow-1" :class="{\'text-muted\': !selectedKey}">\
                [[ selectedDescription ]]\
            </span>\
            <i class="fas fa-chevron-down ms-1" style="font-size:0.7em;"></i>\
        </div>\
        <button class="btn btn-outline-secondary" type="button" @click.stop="clearSelection()" title="Clear">\
            <i class="fa-solid fa-broom"></i>\
        </button>\
    </div>\
    <div v-if="isOpen" style="position:fixed; z-index:9999;" \
         :style="{top: dropTop+\'px\', left: dropLeft+\'px\', width: dropWidth+\'px\'}">\
        <div class="card shadow border" style="max-height:300px; display:flex; flex-direction:column;">\
            <div class="p-2 border-bottom">\
                <input type="text" class="form-control form-control-sm" \
                       v-model="search" \
                       ref="searchInput" \
                       placeholder="Search...">\
            </div>\
            <div style="overflow-y:auto; max-height:250px;">\
                <button v-for="key in filteredOptions" :key="key" \
                        class="list-group-item list-group-item-action border-0 py-1 px-3" \
                        style="font-size:0.9em;" \
                        @mousedown.prevent \
                        @click="selectOption(key)">\
                    [[ key ]] <span class="text-muted" v-if="options[key]">- [[ options[key] ]]</span>\
                </button>\
                <div v-if="filteredOptions.length === 0" class="text-muted text-center py-2" style="font-size:0.85em;">\
                    No matches\
                </div>\
            </div>\
        </div>\
    </div>\
</div>'
});
