// Runtime replacement of [data-name] spans with declined forms from
// assets/translations.json, merged with the reader's own overrides.
import { fetchJSON } from './data.js';

// Pre-redesign key, kept so readers don't lose the names they already set
const OVERRIDES_KEY = 'customNames';
const DEFAULT_FORM = 'однина';
const DEFAULT_CASE = 'називний';

let defaults = {};
let names = {};
let loading = null;

export function loadNames() {
    loading ??= fetchJSON('assets/translations.json').then(data => {
        defaults = data;
        // The old editor saved the whole dictionary, which froze every default
        // name for that reader. Keep only values that really differ.
        const overrides = diff(defaults, readOverrides());
        writeOverrides(overrides);
        names = merge(defaults, overrides);
    });
    return loading;
}

export function applyNames(root = document) {
    root.querySelectorAll('[data-name]').forEach(element => {
        const entry = names[element.dataset.name];
        const form = element.dataset.form || DEFAULT_FORM;
        const nameCase = element.dataset.case || DEFAULT_CASE;
        const text = entry?.[form]?.[nameCase]
            ?? entry?.[form]?.[DEFAULT_CASE]
            ?? entry?.[DEFAULT_FORM]?.[DEFAULT_CASE];
        // Without a translation keep the Ukrainian text already in the chapter file
        if (text) element.textContent = text;
    });
}

export function namesAsJson() {
    return JSON.stringify(names, null, 2);
}

// Throws SyntaxError on invalid JSON
export function saveNamesJson(json) {
    const overrides = diff(defaults, JSON.parse(json));
    writeOverrides(overrides);
    names = merge(defaults, overrides);
    applyNames();
}

export function resetNames() {
    writeOverrides({});
    names = merge(defaults, {});
    applyNames();
}

const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);

// Calls fn(key, form, case, value) for every declined form in a names dictionary
function eachForm(dictionary, fn) {
    if (!isObject(dictionary)) return;
    for (const [key, forms] of Object.entries(dictionary)) {
        if (!isObject(forms)) continue;
        for (const [form, cases] of Object.entries(forms)) {
            if (!isObject(cases)) continue;
            for (const [nameCase, value] of Object.entries(cases)) {
                if (typeof value === 'string' && value.trim()) fn(key, form, nameCase, value.trim());
            }
        }
    }
}

function setForm(dictionary, key, form, nameCase, value) {
    ((dictionary[key] ??= {})[form] ??= {})[nameCase] = value;
}

function diff(base, edited) {
    const result = {};
    eachForm(edited, (key, form, nameCase, value) => {
        if (value !== base[key]?.[form]?.[nameCase]) setForm(result, key, form, nameCase, value);
    });
    return result;
}

function merge(base, overrides) {
    const result = structuredClone(base);
    eachForm(overrides, (key, form, nameCase, value) => setForm(result, key, form, nameCase, value));
    return result;
}

function readOverrides() {
    try {
        return JSON.parse(localStorage.getItem(OVERRIDES_KEY)) ?? {};
    } catch {
        return {};
    }
}

function writeOverrides(overrides) {
    try {
        if (Object.keys(overrides).length) localStorage.setItem(OVERRIDES_KEY, JSON.stringify(overrides));
        else localStorage.removeItem(OVERRIDES_KEY);
    } catch {
        // Storage unavailable: overrides last until the page is closed
    }
}
