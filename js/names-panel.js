// "Імена" tab of the settings drawer: choice of the name set, the reader's own
// names with a declension editor, and a JSON backup of those names.
import { loadChapters } from './data.js';
import { guessForms } from './declension.js';
import {
    CASES, CUSTOM, allSets, exportCustomNames, getDictionary, getNameState, importCustomNames,
    loadNames, nameValue, onNamesChange, pickForm, removeCustomName, resetCustomNames,
    resolveName, setActiveSet, setBaseSet, setCustomName
} from './names.js';
import { getProgress } from './progress.js';
import { escapeHtml } from './ui.js';

const CASE_HINTS = {
    називний: 'хто?', родовий: 'кого?', давальний: 'кому?', знахідний: 'кого?',
    орудний: 'ким?', місцевий: 'на кому?', кличний: 'звертання'
};
const SAMPLE_SIZE = 3;

let panel = null;
let showSpoilers = false;
let visibleKeys = new Set();

// Builds the tab once; resolves when it is ready for focusName()
export async function renderNamesPanel(container) {
    panel = container;
    panel.innerHTML = '<p class="settings-hint">Завантаження…</p>';
    try {
        await loadNames();
        visibleKeys = await readKeys();
    } catch (err) {
        console.error(err);
        panel.innerHTML = '<p class="notice notice--error">Не вдалося завантажити імена. Спробуйте оновити сторінку.</p>';
        return;
    }
    const { sets, categories, names } = getDictionary();
    panel.innerHTML = `
        <section class="settings-section">
            <h3 class="settings-label" id="name-set-label">Набір імен</h3>
            <div class="set-list" role="radiogroup" aria-labelledby="name-set-label">
                ${allSets().map(set => `
                    <label class="set-option">
                        <input type="radio" name="name-set" value="${set.id}">
                        <span class="set-option-text">
                            <span class="set-option-title">${escapeHtml(set.title)}</span>
                            <small data-sample="${set.id}"></small>
                        </span>
                    </label>`).join('')}
            </div>
            <label class="field" data-base-field>
                <span class="field-label">Імена без вашого варіанта брати з набору</span>
                <select data-base>
                    ${sets.map(set => `<option value="${set.id}">${escapeHtml(set.title)}</option>`).join('')}
                </select>
            </label>
            <p class="settings-hint">Натисніть на ім'я в тексті, щоб швидко перемкнути набір. Озвучка завжди використовує локалізовані імена.</p>
        </section>
        <section class="settings-section">
            <h3 class="settings-label">Мої варіанти</h3>
            <input class="input" type="search" placeholder="Пошук імені" aria-label="Пошук імені" data-search>
            ${categories.map(category => `
                <div class="name-group" data-category="${category.id}">
                    <h4 class="name-group-title">${escapeHtml(category.title)}</h4>
                    ${Object.entries(names)
                        .filter(([, entry]) => entry.category === category.id)
                        .map(([key]) => rowHtml(key)).join('')}
                </div>`).join('')}
            <p class="settings-hint" data-spoiler-note hidden></p>
        </section>
        <section class="settings-section">
            <details class="names-json">
                <summary>Резервна копія моїх імен (JSON)</summary>
                <p class="settings-hint">Скопіюйте цей текст, щоб перенести свої імена на інший пристрій, або вставте збережений раніше.</p>
                <textarea class="input" spellcheck="false" rows="8" aria-label="Мої імена у форматі JSON"></textarea>
                <div class="settings-actions">
                    <button class="button button--small" data-import>Застосувати</button>
                    <button class="button button--small button--ghost" data-reset>Скинути всі мої імена</button>
                </div>
                <p class="settings-hint" role="status" data-json-status></p>
            </details>
        </section>`;

    panel.addEventListener('change', event => {
        if (event.target.name === 'name-set') setActiveSet(event.target.value);
        if (event.target.matches('[data-base]')) setBaseSet(event.target.value);
    });
    panel.querySelector('[data-search]').addEventListener('input', refreshRows);
    panel.querySelectorAll('.name-row').forEach(row => {
        row.addEventListener('toggle', () => {
            if (row.open && !row.querySelector('.name-editor').childElementCount) buildEditor(row);
        });
    });
    panel.querySelector('[data-spoiler-note]').addEventListener('click', event => {
        if (!event.target.closest('button')) return;
        showSpoilers = true;
        refreshRows();
    });
    setupBackup(panel.querySelector('.names-json'));

    onNamesChange(refresh);
    refresh();
}

// Opens the editor of one name (from the popover in the text)
export function focusName(key) {
    const row = panel?.querySelector(`.name-row[data-key="${CSS.escape(key)}"]`);
    if (!row) return;
    row.hidden = false; // the reader has just seen this name in the text
    row.open = true;
    if (!row.querySelector('.name-editor').childElementCount) buildEditor(row);
    row.scrollIntoView({ block: 'start' });
    row.querySelector('[data-nominative]').focus({ preventScroll: true });
}

function rowHtml(key) {
    return `
        <details class="name-row" data-key="${escapeHtml(key)}">
            <summary>
                <span class="name-row-original">${escapeHtml(pickForm(nameValue(key, 'original')))}</span>
                <span class="badge" data-own-badge hidden>моє</span>
                <span class="name-row-current" data-current></span>
            </summary>
            <div class="name-editor"></div>
        </details>`;
}

// Names first seen in chapters the reader hasn't opened yet stay hidden
async function readKeys() {
    const data = await loadChapters();
    const index = new Map(data.chapters.map((chapter, i) => [chapter.id, i]));
    const opened = Object.keys(getProgress().chapters).map(id => index.get(id) ?? -1);
    const furthest = Math.max(0, ...opened);
    const keys = Object.entries(getDictionary().names)
        .filter(([, entry]) => (index.get(entry.firstSeen) ?? 0) <= furthest)
        .map(([key]) => key);
    return new Set(keys);
}

function refresh() {
    const state = getNameState();
    panel.querySelectorAll('input[name="name-set"]').forEach(input => {
        input.checked = input.value === state.set;
    });
    const base = panel.querySelector('[data-base]');
    base.value = state.base;
    panel.querySelector('[data-base-field]').hidden = state.set !== CUSTOM;

    const samples = Object.keys(getDictionary().names).filter(key => visibleKeys.has(key)).slice(0, SAMPLE_SIZE);
    panel.querySelectorAll('[data-sample]').forEach(element => {
        element.textContent = samples.map(key => resolveName(key, 'однина', 'називний', element.dataset.sample)).join(', ');
    });
    panel.querySelectorAll('.name-row').forEach(row => {
        const key = row.dataset.key;
        row.querySelector('[data-current]').textContent = resolveName(key, 'однина', 'називний');
        row.querySelector('[data-own-badge]').hidden = !state.custom[key];
    });
    refreshRows();
}

function refreshRows() {
    const query = panel.querySelector('[data-search]').value.trim().toLowerCase();
    let hidden = 0;
    panel.querySelectorAll('.name-row').forEach(row => {
        const key = row.dataset.key;
        const spoiler = !showSpoilers && !visibleKeys.has(key) && !row.open;
        if (spoiler) hidden++;
        const texts = allSets().map(set => resolveName(key, 'однина', 'називний', set.id));
        const matches = !query || texts.some(text => text?.toLowerCase().includes(query));
        row.hidden = spoiler || !matches;
    });
    panel.querySelectorAll('.name-group').forEach(group => {
        group.hidden = !group.querySelector('.name-row:not([hidden])');
    });
    const note = panel.querySelector('[data-spoiler-note]');
    note.hidden = hidden === 0;
    note.innerHTML = `Приховано імен із глав, які ви ще не читали: ${hidden}. <button class="link-button">Показати всі</button>`;
}

function caseField(number, nameCase) {
    return `
        <label class="field">
            <span class="field-label">${nameCase} <small>${CASE_HINTS[nameCase]}</small></span>
            <input class="input" type="text" data-number="${number}" data-case="${nameCase}" autocomplete="off" spellcheck="false">
        </label>`;
}

function buildEditor(row) {
    const key = row.dataset.key;
    const editor = row.querySelector('.name-editor');
    editor.innerHTML = `
        <label class="field">
            <span class="field-label">Своє ім'я</span>
            <input class="input" type="text" data-nominative autocomplete="off" spellcheck="false">
        </label>
        <label class="switch">
            <input type="checkbox" data-indeclinable>
            <span>Не відмінюється</span>
        </label>
        <div data-cases>
            <div class="case-grid">${CASES.slice(1).map(nameCase => caseField('однина', nameCase)).join('')}</div>
            <details class="plural">
                <summary>Множина</summary>
                <div class="case-grid">${CASES.map(nameCase => caseField('множина', nameCase)).join('')}</div>
            </details>
            <p class="settings-hint">Відмінки підставляються автоматично — перевірте їх.</p>
        </div>
        <p class="settings-hint">Зберігайте рід імені: слова довкола нього в тексті не змінюються.</p>
        <div class="settings-actions">
            <button class="button button--small" data-save>Зберегти</button>
            <button class="button button--small button--ghost" data-remove>Прибрати моє</button>
        </div>
        <p class="settings-hint" role="status" data-status></p>`;

    const nominative = editor.querySelector('[data-nominative]');
    const indeclinable = editor.querySelector('[data-indeclinable]');
    const inputs = [...editor.querySelectorAll('input[data-case]')];
    const status = editor.querySelector('[data-status]');
    const own = getNameState().custom[key];
    // Start from the reader's name, or from the name currently shown in the text
    const start = own ?? nameValue(key);
    nominative.value = pickForm(start) ?? '';
    indeclinable.checked = typeof start === 'string';
    inputs.forEach(input => {
        input.value = pickForm(start, input.dataset.number, input.dataset.case) ?? '';
        // Fields typed by the reader are kept when the nominative changes
        input.addEventListener('input', () => { input.dataset.touched = '1'; });
    });
    editor.querySelector('[data-remove]').hidden = !own;

    nominative.addEventListener('input', () => {
        const guess = guessForms(nominative.value);
        inputs.forEach(input => {
            if (!input.dataset.touched) {
                input.value = guess?.[input.dataset.number][input.dataset.case] ?? nominative.value.trim();
            }
        });
    });
    const showCases = () => { editor.querySelector('[data-cases]').hidden = indeclinable.checked; };
    indeclinable.addEventListener('change', showCases);
    showCases();

    editor.querySelector('[data-save]').addEventListener('click', () => {
        const name = nominative.value.trim();
        if (!name) {
            status.textContent = "Введіть ім'я.";
            nominative.focus();
            return;
        }
        const wasCustom = getNameState().set === CUSTOM;
        let value = name;
        if (!indeclinable.checked) {
            value = { однина: { називний: name }, множина: {} };
            for (const input of inputs) {
                value[input.dataset.number][input.dataset.case] = input.value.trim() || name;
            }
        }
        setCustomName(key, value);
        editor.querySelector('[data-remove]').hidden = false;
        status.textContent = wasCustom ? 'Збережено.' : 'Збережено. Увімкнено набір «Мої».';
    });
    editor.querySelector('[data-remove]').addEventListener('click', () => {
        removeCustomName(key);
        editor.innerHTML = '';
        buildEditor(row);
        row.querySelector('[data-status]').textContent = 'Ваш варіант прибрано.';
    });
}

function setupBackup(details) {
    const textarea = details.querySelector('textarea');
    const status = details.querySelector('[data-json-status]');
    details.addEventListener('toggle', () => {
        if (!details.open) return;
        textarea.value = exportCustomNames();
        status.textContent = '';
    });
    details.querySelector('[data-import]').addEventListener('click', () => {
        try {
            importCustomNames(textarea.value);
            textarea.value = exportCustomNames();
            status.textContent = 'Застосовано.';
        } catch {
            status.textContent = 'Не вдалося прочитати JSON — нічого не змінено.';
        }
    });
    details.querySelector('[data-reset]').addEventListener('click', () => {
        if (!confirm('Видалити всі ваші варіанти імен?')) return;
        resetCustomNames();
        textarea.value = exportCustomNames();
        panel.querySelectorAll('.name-editor').forEach(editor => { editor.innerHTML = ''; });
        panel.querySelectorAll('.name-row').forEach(row => { row.open = false; });
        status.textContent = 'Ваші варіанти видалено.';
    });
}
