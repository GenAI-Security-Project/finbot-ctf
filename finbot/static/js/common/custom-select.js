/**
 * CustomSelect - Accessible custom dropdown replacing native <select>.
 *
 * Provides full keyboard navigation (Arrow keys, Home/End, Enter/Space,
 * Escape, Tab, type-ahead search), ARIA roles/states for screen readers,
 * and automatic viewport-aware positioning.
 *
 * HTML contract:
 *   <input type="hidden" id="fieldName" name="fieldName" required>
 *   <div class="custom-select" data-for="fieldName" data-placeholder="Choose…">
 *     <div class="custom-select-trigger vendor-input"
 *          role="combobox" aria-expanded="false" aria-haspopup="listbox"
 *          aria-controls="fieldName_listbox" aria-labelledby="fieldName_label"
 *          tabindex="0">
 *       <span class="custom-select-display">Choose…</span>
 *       <svg class="custom-select-arrow" …>…</svg>
 *     </div>
 *     <ul id="fieldName_listbox" class="custom-select-listbox"
 *         role="listbox" aria-labelledby="fieldName_label" hidden>
 *       <li role="option" id="fieldName_opt_val" data-value="val">Label</li>
 *     </ul>
 *   </div>
 *
 * JS:
 *   CustomSelect.initAll();
 *   CustomSelect.getInstance('fieldName').setValue('val');
 */

class CustomSelect {
    static _instances = new Map();

    static initAll(selector = '.custom-select') {
        document.querySelectorAll(selector).forEach(el => {
            if (!CustomSelect._instances.has(el.dataset.for)) {
                new CustomSelect(el);
            }
        });
    }

    static getInstance(name) {
        return CustomSelect._instances.get(name);
    }

    constructor(wrapper) {
        this.wrapper = wrapper;
        this.name = wrapper.dataset.for;
        this.placeholder = wrapper.dataset.placeholder || 'Select\u2026';
        this.hiddenInput = document.getElementById(this.name);

        this.trigger = wrapper.querySelector('.custom-select-trigger');
        this.display = wrapper.querySelector('.custom-select-display');
        this.arrow = wrapper.querySelector('.custom-select-arrow');
        this.listbox = wrapper.querySelector('.custom-select-listbox');
        this.options = Array.from(this.listbox.querySelectorAll('[role="option"]'));

        this.isOpen = false;
        this.selectedIdx = -1;
        this.activeIdx = -1;
        this._searchStr = '';
        this._searchTimer = null;

        this._ensureLiveRegion();
        this._bindEvents();
        this._linkLabel();

        if (this.hiddenInput.value) {
            this.setValue(this.hiddenInput.value, false);
        }

        CustomSelect._instances.set(this.name, this);
    }

    // ── Public API ──────────────────────────────────────────────────

    toggle() {
        this.isOpen ? this.close() : this.open();
    }

    open() {
        if (this.isOpen) return;
        this.isOpen = true;
        this.listbox.removeAttribute('hidden');
        this.trigger.setAttribute('aria-expanded', 'true');
        this.wrapper.classList.add('custom-select-open');

        this._updatePosition();

        const start = this.selectedIdx >= 0 ? this.selectedIdx : 0;
        if (this.options.length) {
            this._setActive(start);
            this._scrollToActive();
        }
    }

    close() {
        if (!this.isOpen) return;
        this.isOpen = false;
        this.listbox.setAttribute('hidden', '');
        this.trigger.setAttribute('aria-expanded', 'false');
        this.trigger.removeAttribute('aria-activedescendant');
        this.wrapper.classList.remove('custom-select-open');
        this.activeIdx = -1;

        this.options.forEach(o => o.classList.remove('custom-select-option-active'));
    }

    select(index) {
        if (index < 0 || index >= this.options.length) return;

        if (this.selectedIdx >= 0) {
            this.options[this.selectedIdx].setAttribute('aria-selected', 'false');
            this.options[this.selectedIdx].classList.remove('custom-select-option-selected');
        }

        this.selectedIdx = index;
        const opt = this.options[index];

        opt.setAttribute('aria-selected', 'true');
        opt.classList.add('custom-select-option-selected');

        this.display.textContent = opt.textContent;
        this.display.classList.remove('custom-select-placeholder');

        const value = opt.dataset.value;
        this.hiddenInput.value = value;

        this._clearError();
        this._announce(opt.textContent + ' selected');
    }

    setValue(value, announce = true) {
        if (!value) {
            this._reset();
            return;
        }
        const idx = this.options.findIndex(o => o.dataset.value === value);
        if (idx >= 0) {
            this.select(idx);
            if (!announce) this._liveRegion.textContent = '';
        }
    }

    destroy() {
        document.removeEventListener('click', this._onOutsideClick);
        document.removeEventListener('keydown', this._onDocKeyDown);
        CustomSelect._instances.delete(this.name);
    }

    // ── Private ─────────────────────────────────────────────────────

    _reset() {
        if (this.selectedIdx >= 0) {
            this.options[this.selectedIdx].setAttribute('aria-selected', 'false');
            this.options[this.selectedIdx].classList.remove('custom-select-option-selected');
        }
        this.selectedIdx = -1;
        this.display.textContent = this.placeholder;
        this.display.classList.add('custom-select-placeholder');
        this.hiddenInput.value = '';
    }

    _bindEvents() {
        this.trigger.addEventListener('click', () => this.toggle());
        this.trigger.addEventListener('keydown', e => this._onKeyDown(e));

        this.options.forEach((opt, i) => {
            opt.addEventListener('click', e => {
                e.stopPropagation();
                this.select(i);
                this.close();
                this.trigger.focus();
            });
            opt.addEventListener('mouseenter', () => this._setActive(i));
        });

        this._onOutsideClick = e => {
            if (!this.wrapper.contains(e.target)) this.close();
        };
        document.addEventListener('click', this._onOutsideClick);

        this._onDocKeyDown = e => {
            if (this.isOpen && e.key === 'Tab') this.close();
        };
        document.addEventListener('keydown', this._onDocKeyDown);

        this.hiddenInput.addEventListener('change', () => {
            this.setValue(this.hiddenInput.value, false);
        });
    }

    _linkLabel() {
        const labelId = this.trigger.getAttribute('aria-labelledby');
        if (!labelId) return;
        const label = document.getElementById(labelId);
        if (!label) return;
        label.style.cursor = 'pointer';
        label.addEventListener('click', () => {
            this.trigger.focus();
        });
    }

    _setActive(index) {
        if (this.activeIdx >= 0 && this.activeIdx < this.options.length) {
            this.options[this.activeIdx].classList.remove('custom-select-option-active');
        }
        this.activeIdx = index;
        const opt = this.options[index];
        opt.classList.add('custom-select-option-active');
        this.trigger.setAttribute('aria-activedescendant', opt.id);
    }

    _scrollToActive() {
        if (this.activeIdx < 0) return;
        this.options[this.activeIdx].scrollIntoView({ block: 'nearest' });
    }

    _onKeyDown(e) {
        const { key } = e;
        const last = this.options.length - 1;

        switch (key) {
            case 'Enter':
            case ' ':
                e.preventDefault();
                if (this.isOpen && this.activeIdx >= 0) {
                    this.select(this.activeIdx);
                    this.close();
                } else {
                    this.open();
                }
                break;

            case 'ArrowDown':
                e.preventDefault();
                if (!this.isOpen) {
                    this.open();
                } else {
                    this._setActive(Math.min(this.activeIdx + 1, last));
                    this._scrollToActive();
                }
                break;

            case 'ArrowUp':
                e.preventDefault();
                if (!this.isOpen) {
                    this.open();
                } else {
                    this._setActive(Math.max(this.activeIdx - 1, 0));
                    this._scrollToActive();
                }
                break;

            case 'Home':
                e.preventDefault();
                if (this.isOpen) { this._setActive(0); this._scrollToActive(); }
                break;

            case 'End':
                e.preventDefault();
                if (this.isOpen) { this._setActive(last); this._scrollToActive(); }
                break;

            case 'Escape':
                if (this.isOpen) {
                    e.preventDefault();
                    this.close();
                    this.trigger.focus();
                }
                break;

            default:
                if (key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
                    e.preventDefault();
                    this._typeAhead(key);
                }
                break;
        }
    }

    _typeAhead(char) {
        this._searchStr += char.toLowerCase();
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => { this._searchStr = ''; }, 600);

        const match = this.options.findIndex(
            o => o.textContent.trim().toLowerCase().startsWith(this._searchStr)
        );
        if (match >= 0) {
            if (!this.isOpen) this.open();
            this._setActive(match);
            this._scrollToActive();
        }
    }

    _updatePosition() {
        const rect = this.trigger.getBoundingClientRect();
        const below = window.innerHeight - rect.bottom;

        this.listbox.classList.toggle('custom-select-listbox-above', below < 260 && rect.top > below);
    }

    _clearError() {
        this.hiddenInput.classList.remove('border-red-400');
        const err = this.hiddenInput.parentNode.querySelector('.field-error');
        if (err) err.remove();
    }

    _ensureLiveRegion() {
        let region = document.getElementById('custom-select-live');
        if (!region) {
            region = document.createElement('div');
            region.id = 'custom-select-live';
            region.className = 'sr-only';
            region.setAttribute('role', 'status');
            region.setAttribute('aria-live', 'polite');
            document.body.appendChild(region);
        }
        this._liveRegion = region;
    }

    _announce(msg) {
        this._liveRegion.textContent = '';
        requestAnimationFrame(() => { this._liveRegion.textContent = msg; });
    }
}

window.CustomSelect = CustomSelect;
