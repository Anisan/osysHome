Vue.component('select-with-filter', {
    delimiters: ['[[', ']]'],
    props: ['options','value','placeholder'],
    data() {
        return {
            search: '',
            isOpen: false,
            selectedKey: null,
            initialSet: true
        };
    },
    watch: {
        value(newVal) {
            console.log(newVal)
            this.selectedKey = newVal;
        },
        selectedKey(newVal) {
            if (!this.initialSet) {
                this.$emit('changed', newVal);
            }
            this.$emit('input', newVal);
            this.initialSet = false; // После первого изменения установим в false
        }
    },
    computed: {
        filteredOptions() {
            return Object.keys(this.options).filter(key => 
                (key + this.options[key]).toLowerCase().includes(this.search.toLowerCase())
            );
            
        },
        selectedDescription() {
            return this.selectedKey ? this.selectedKey + " - " + this.options[this.selectedKey] : this.placeholder;
        }
    },
    methods: {
        selectOption(key) {
            this.selectedKey = key;
            this.isOpen = false;
            this.search = '';
        },
        toggleDropdown() {
            this.isOpen = !this.isOpen;
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
    template: `
        <div class="input-group">
            <input 
                type="text" 
                v-model="search" 
                @focus="isOpen = true" 
                @input="isOpen = true"
                class="form-control me-auto" 
                :placeholder="selectedDescription"
            >
            <button class="btn btn-outline-secondary" type="button" @click="selectedKey=null"><i class="fa-solid fa-broom"></i></button>
            <div v-if="isOpen" class="list-group card position-absolute w-150" style="z-index: 1050;">
                <button 
                    v-for="key in filteredOptions" 
                    :key="key" 
                    class="list-group-item list-group-item-action"
                    @mousedown.prevent
                    @click="selectOption(key)"
                >
                    [[ key ]] - [[ options[key] ]]
                </button>
            </div>
        </div>
    `
});