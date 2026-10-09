// Name sets: every [data-name] span shows its key in the set the reader chose.
// Dictionary sets come from assets/names.json; the "custom" set is the reader's
// own names on top of a base set, kept in localStorage.
import { fetchJSON } from './data.js';
import { load, save } from './storage.js';

export const FORMS = ['однина', 'множина'];
export const CASES = ['називний', 'родовий', 'давальний', 'знахідний', 'орудний', 'місцевий', 'кличний'];
export const CUSTOM = 'custom';
const CUSTOM_SET = { id: CUSTOM, title: 'Мої', hint: 'Ваші власні варіанти' };
const STATE_KEY = 'names';
const DEFAULT_SET = 'localized';

let dictionary = null;
let loading = null;
let state = readState();
const listeners = new Set();

export function loadNames() {
    loading ??= fetchJSON('assets/names.json').then(data => {
        dictionary = data;
        // Drop set ids that no longer exist in the dictionary
        if (!isDictionarySet(state.base)) state.base = DEFAULT_SET;
        if (state.set !== CUSTOM && !isDictionarySet(state.set)) state.set = DEFAULT_SET;
        return data;
    });
    return loading;
}

export function getDictionary() {
    return dictionary;
}

export function getNameState() {
    return state;
}

export function allSets() {
    return [...dictionary.sets, CUSTOM_SET];
}

export function onNamesChange(listener) {
    listeners.add(listener);
}

// A value is a string (indeclinable) or { однина, множина }, where each number
// is a string or a table of the seven cases. Missing parts fall back to the
// nominative singular.
export function pickForm(value, form = FORMS[0], nameCase = CASES[0]) {
    if (value == null || typeof value === 'string') return value ?? null;
    const number = value[form] ?? value[FORMS[0]];
    if (number == null || typeof number === 'string') return number ?? null;
    return number[nameCase] ?? number[CASES[0]] ?? null;
}

// Value of a name in a set; for the custom set, the reader's own value or the base set's
export function nameValue(key, setId = state.set) {
    const entry = dictionary?.names[key];
    if (!entry) return null;
    if (setId === CUSTOM) return state.custom[key] ?? nameValue(key, state.base);
    if (setId === 'original') return entry.original ?? key;
    if (setId === 'translit') return entry.translit ?? entry.localized;
    return entry.localized;
}

export function resolveName(key, form, nameCase, setId = state.set) {
    return pickForm(nameValue(key, setId), form, nameCase)
        ?? pickForm(dictionary?.names[key]?.localized, form, nameCase);
}

export function applyNames(root = document) {
    if (!dictionary) return;
    root.querySelectorAll('[data-name]').forEach(element => {
        const key = element.dataset.name;
        if (!dictionary.names[key]) return; // keep the text written in the chapter
        // Remember once whether the chapter capitalizes this occurrence (sentence start)
        element.dataset.capital ??= /^\p{Lu}/u.test(element.textContent) ? '1' : '';
        let text = resolveName(key, element.dataset.form, element.dataset.case);
        if (!text) return;
        if (element.dataset.capital) text = text[0].toUpperCase() + text.slice(1);
        element.textContent = text;
        if (!element.hasAttribute('tabindex')) {
            element.tabIndex = 0;
            element.setAttribute('role', 'button');
            element.setAttribute('aria-haspopup', 'dialog');
        }
    });
}

export function setActiveSet(id) {
    update({ set: id });
}

export function setBaseSet(id) {
    if (isDictionarySet(id)) update({ base: id });
}

// Saving an own name switches to the custom set, built on the set in use
export function setCustomName(key, value) {
    const custom = { ...state.custom, [key]: value };
    update(state.set === CUSTOM ? { custom } : { custom, set: CUSTOM, base: state.set });
}

export function removeCustomName(key) {
    const { [key]: _removed, ...custom } = state.custom;
    update({ custom });
}

export function resetCustomNames() {
    update({ custom: {}, set: state.set === CUSTOM ? state.base : state.set });
}

export function exportCustomNames() {
    return JSON.stringify({ base: state.base, custom: state.custom }, null, 2);
}

// Throws on invalid JSON or an unexpected shape
export function importCustomNames(json) {
    const data = JSON.parse(json);
    if (!isObject(data) || !isObject(data.custom)) throw new Error('Expected {"custom": {...}}');
    const custom = {};
    for (const [key, value] of Object.entries(data.custom)) {
        if (isValidValue(value)) custom[key] = value;
    }
    update({ custom, set: CUSTOM, base: isDictionarySet(data.base) ? data.base : state.base });
}

function update(patch) {
    state = { ...state, ...patch };
    save(STATE_KEY, state);
    applyNames();
    listeners.forEach(listener => listener(state));
}

function readState() {
    // The pre-sets editor stored overrides under this key; they are not migrated
    try {
        localStorage.removeItem('customNames');
    } catch {
        // Storage unavailable
    }
    const saved = load(STATE_KEY, {});
    return {
        set: typeof saved.set === 'string' ? saved.set : DEFAULT_SET,
        base: typeof saved.base === 'string' ? saved.base : DEFAULT_SET,
        custom: isObject(saved.custom) ? saved.custom : {}
    };
}

function isDictionarySet(id) {
    return dictionary ? dictionary.sets.some(set => set.id === id) : true;
}

// Function declarations: readState() uses them while the module is initializing
function isObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isText(value) {
    return typeof value === 'string' && value.trim() !== '';
}

function isValidValue(value) {
    if (isText(value)) return true;
    if (!isObject(value)) return false;
    const singular = value[FORMS[0]];
    if (!isText(singular) && !isObject(singular)) return false;
    return Object.values(value).every(number =>
        isText(number) || (isObject(number) && Object.values(number).every(isText)));
}
