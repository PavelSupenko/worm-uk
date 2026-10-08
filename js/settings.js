// Reader settings (theme, font, size, spacing...) and the settings drawer.
// Defaults and applying to <html> live in boot.js so they work before paint.
import { save } from './storage.js';
import { loadNames, namesAsJson, saveNamesJson, resetNames } from './names.js';
import { icon, setupDrawer } from './ui.js';

const { load, apply } = window.WormSettings;
const SIZE_MIN = 14;
const SIZE_MAX = 28;
const CHOICES = {
    theme: { label: 'Тема', options: [['dark', 'Темна'], ['light', 'Світла'], ['sepia', 'Сепія']] },
    font: { label: 'Шрифт', options: [['serif', 'З засічками'], ['sans', 'Без засічок']] },
    spacing: { label: 'Міжрядковий інтервал', options: [['compact', 'Щільно'], ['normal', 'Звичайно'], ['relaxed', 'Просторо']] }
};

let settings = load();
const listeners = new Set();

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

export function initSettingsPanel(openButton) {
    const dialog = document.createElement('dialog');
    dialog.className = 'drawer drawer--right';
    dialog.setAttribute('aria-labelledby', 'settings-heading');
    dialog.innerHTML = `
        <div class="drawer-body">
            <div class="drawer-head">
                <h2 id="settings-heading" class="drawer-title">Налаштування</h2>
                <button class="icon-button" data-close aria-label="Закрити">${icon('close')}</button>
            </div>
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
            <section class="settings-section">
                <h3 class="settings-label">Імена персонажів</h3>
                <p class="settings-hint">Зручний вибір перекладу імен з'явиться в наступному оновленні. Поки що їх можна змінити вручну.</p>
                <details class="names-json">
                    <summary>Редагувати імена (JSON)</summary>
                    <textarea spellcheck="false" rows="12" aria-label="Імена у форматі JSON"></textarea>
                    <div class="settings-actions">
                        <button class="button button--small" data-names-save>Зберегти</button>
                        <button class="button button--small button--ghost" data-names-reset>Скинути</button>
                    </div>
                    <p class="settings-hint" data-names-status role="status"></p>
                </details>
            </section>
        </div>`;
    document.body.append(dialog);
    setupDrawer(dialog, openButton);

    dialog.addEventListener('click', event => {
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

    initNamesEditor(dialog.querySelector('.names-json'));

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

// Temporary raw-JSON editor; to be replaced by the name sets UI
function initNamesEditor(details) {
    const textarea = details.querySelector('textarea');
    const status = details.querySelector('[data-names-status]');
    details.addEventListener('toggle', async () => {
        if (!details.open) return;
        status.textContent = '';
        try {
            await loadNames();
            textarea.value = namesAsJson();
        } catch {
            status.textContent = 'Не вдалося завантажити імена.';
        }
    });
    details.querySelector('[data-names-save]').addEventListener('click', () => {
        try {
            saveNamesJson(textarea.value);
            status.textContent = 'Збережено.';
        } catch {
            status.textContent = 'Помилка у форматі JSON — зміни не збережено.';
        }
    });
    details.querySelector('[data-names-reset]').addEventListener('click', () => {
        resetNames();
        textarea.value = namesAsJson();
        status.textContent = 'Повернуто переклад за замовчуванням.';
    });
}
