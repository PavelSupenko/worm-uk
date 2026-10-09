// Reader settings (theme, font, size, spacing...) and the settings drawer with
// its "Читання" and "Імена" tabs. Defaults and applying to <html> live in
// boot.js so they work before paint.
import { focusName, renderNamesPanel } from './names-panel.js';
import { save } from './storage.js';
import { icon, setupDrawer } from './ui.js';

const { load, apply } = window.WormSettings;
const SIZE_MIN = 14;
const SIZE_MAX = 28;
const CHOICES = {
    theme: { label: 'Тема', options: [['dark', 'Темна'], ['light', 'Світла'], ['sepia', 'Сепія']] },
    font: { label: 'Шрифт', options: [['serif', 'З засічками'], ['sans', 'Без засічок']] },
    spacing: { label: 'Міжрядковий інтервал', options: [['compact', 'Щільно'], ['normal', 'Звичайно'], ['relaxed', 'Просторо']] }
};
const TABS = [['reading', 'Читання'], ['names', 'Імена']];

let settings = load();
const listeners = new Set();
let dialog = null;
let namesReady = null;

export function getSettings() {
    return settings;
}

export function onSettingsChange(listener) {
    listeners.add(listener);
}

export function updateSettings(patch) {
    settings = { ...settings, ...patch };
    save('settings', settings); // same key as WormSettings.KEY in boot.js
    apply(settings);
    listeners.forEach(listener => listener(settings));
}

// Opens the drawer, optionally on a tab and at one name's editor
export async function openSettings({ tab = 'reading', nameKey = null } = {}) {
    if (!dialog.open) dialog.showModal();
    selectTab(tab);
    if (nameKey) {
        await namesReady;
        focusName(nameKey);
    }
}

export function initSettingsPanel(openButton) {
    dialog = document.createElement('dialog');
    dialog.className = 'drawer drawer--right';
    dialog.setAttribute('aria-labelledby', 'settings-heading');
    dialog.innerHTML = `
        <div class="drawer-body">
            <div class="drawer-head drawer-head--tabs">
                <div class="drawer-head-row">
                    <h2 id="settings-heading" class="drawer-title">Налаштування</h2>
                    <button class="icon-button" data-close aria-label="Закрити">${icon('close')}</button>
                </div>
                <div class="tabs" role="tablist" aria-label="Розділи налаштувань">
                    ${TABS.map(([id, label]) => `
                        <button role="tab" id="settings-tab-${id}" aria-controls="settings-panel-${id}" data-tab="${id}">${label}</button>`).join('')}
                </div>
            </div>
            <div role="tabpanel" id="settings-panel-reading" aria-labelledby="settings-tab-reading">
                ${segmented('theme')}
                ${segmented('font')}
                <section class="settings-section">
                    <h3 class="settings-label">Розмір тексту</h3>
                    <div class="stepper">
                        <button class="chip" data-size-step="-1" aria-label="Зменшити текст">A−</button>
                        <output class="stepper-value" data-size-value></output>
                        <button class="chip" data-size-step="1" aria-label="Збільшити текст">A+</button>
                    </div>
                </section>
                ${segmented('spacing')}
                <section class="settings-section">
                    <label class="switch">
                        <input type="checkbox" data-highlight-names>
                        <span>Виділяти імена кольором</span>
                    </label>
                </section>
            </div>
            <div role="tabpanel" id="settings-panel-names" aria-labelledby="settings-tab-names" hidden></div>
        </div>`;
    document.body.append(dialog);
    setupDrawer(dialog, openButton);

    dialog.addEventListener('click', event => {
        const tab = event.target.closest('[data-tab]');
        if (tab) selectTab(tab.dataset.tab);
        const option = event.target.closest('[data-option]');
        if (option) updateSettings({ [option.dataset.setting]: option.dataset.option });
        const step = event.target.closest('[data-size-step]');
        if (step) {
            const size = Math.min(SIZE_MAX, Math.max(SIZE_MIN, settings.size + Number(step.dataset.sizeStep)));
            updateSettings({ size });
        }
    });
    const highlight = dialog.querySelector('[data-highlight-names]');
    highlight.addEventListener('change', () => updateSettings({ highlightNames: highlight.checked }));

    const render = () => {
        dialog.querySelectorAll('[data-option]').forEach(button => {
            button.setAttribute('aria-pressed', String(settings[button.dataset.setting] === button.dataset.option));
        });
        dialog.querySelector('[data-size-value]').textContent = `${settings.size} px`;
        dialog.querySelector('[data-size-step="-1"]').disabled = settings.size <= SIZE_MIN;
        dialog.querySelector('[data-size-step="1"]').disabled = settings.size >= SIZE_MAX;
        highlight.checked = settings.highlightNames;
    };
    onSettingsChange(render);
    render();
    selectTab('reading');
}

function selectTab(id) {
    dialog.querySelectorAll('[role="tab"]').forEach(tab => {
        tab.setAttribute('aria-selected', String(tab.dataset.tab === id));
    });
    dialog.querySelectorAll('[role="tabpanel"]').forEach(panel => {
        panel.hidden = panel.id !== `settings-panel-${id}`;
    });
    // The names tab needs names.json, so it is built on first use
    if (id === 'names') namesReady ??= renderNamesPanel(dialog.querySelector('#settings-panel-names'));
}

function segmented(setting) {
    const { label, options } = CHOICES[setting];
    return `
        <section class="settings-section">
            <h3 class="settings-label" id="label-${setting}">${label}</h3>
            <div class="segmented" role="group" aria-labelledby="label-${setting}">
                ${options.map(([value, text]) => `<button data-setting="${setting}" data-option="${value}">${text}</button>`).join('')}
            </div>
        </section>`;
}
