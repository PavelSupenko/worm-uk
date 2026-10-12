// Entry point of glossary.html: characters, capes, groups and terms from the
// chapters the reader has opened. Capes, groups and terms come from
// assets/names.json (shown in the reader's name set), descriptions and the
// civilian characters from assets/glossary.json.
import { chapterTitle, chapterUrl, fetchJSON, loadChapters } from './data.js';
import { allSets, getDictionary, loadNames, nameValue, onNamesChange, pickForm, resolveName } from './names.js';
import { registerServiceWorker } from './offline.js';
import { furthestOpened } from './progress.js';
import { initSettingsPanel } from './settings.js';
import { escapeHtml } from './ui.js';

const container = document.getElementById('glossary');
let showSpoilers = false;
let model = null;

initSettingsPanel(document.getElementById('open-settings'));
registerServiceWorker();

Promise.all([loadChapters(), loadNames(), fetchJSON('assets/glossary.json')])
    .then(([data, , glossary]) => {
        model = { data, glossary };
        render();
        onNamesChange(render);
    })
    .catch(err => {
        console.error(err);
        container.innerHTML = '<p class="notice notice--error">Не вдалося завантажити глосарій. Спробуйте оновити сторінку.</p>';
    });

container.addEventListener('click', event => {
    if (event.target.closest('[data-show-spoilers]')) {
        showSpoilers = !showSpoilers;
        render();
    }
});

function render() {
    const { data, glossary } = model;
    const index = new Map(data.chapters.map((chapter, i) => [chapter.id, i]));
    const furthest = furthestOpened(data);
    const seen = entry => showSpoilers || (index.get(entry.firstSeen) ?? Infinity) <= furthest;
    const { categories, names } = getDictionary();

    const groups = [{
        title: 'Персонажі',
        entries: Object.entries(glossary.characters).map(([key, entry]) => ({
            key, title: entry.name, firstSeen: entry.firstSeen, description: entry.description, variants: []
        }))
    }, ...categories.map(category => ({
        title: category.title,
        entries: Object.entries(names)
            .filter(([, entry]) => entry.category === category.id)
            .map(([key, entry]) => ({
                key,
                title: capitalize(resolveName(key, 'однина', 'називний')),
                firstSeen: entry.firstSeen,
                description: glossary.names[key] ?? '',
                variants: variants(key)
            }))
    }))];

    let hidden = 0;
    const sections = groups.map(group => {
        const visible = group.entries.filter(seen);
        hidden += group.entries.length - visible.length;
        if (!visible.length) return '';
        // By first appearance; within a chapter in the data files' order (the narrator first)
        visible.sort((a, b) => (index.get(a.firstSeen) ?? 0) - (index.get(b.firstSeen) ?? 0));
        return `
            <section class="section">
                <h2 class="section-title">${escapeHtml(group.title)}</h2>
                <dl class="glossary-list">${visible.map(entry => entryHtml(entry, data)).join('')}</dl>
            </section>`;
    }).join('');

    const toggle = showSpoilers
        ? '<button class="link-button" data-show-spoilers>Сховати спойлери</button>'
        : hidden ? `Ще ${hidden} ${plural(hidden, 'запис', 'записи', 'записів')} з глав, які ви не відкривали. <button class="link-button" data-show-spoilers>Показати (спойлери)</button>` : '';
    container.innerHTML = `${sections || '<p class="notice">Тут з’являться персонажі й терміни з глав, які ви відкриєте.</p>'}
        ${toggle ? `<p class="glossary-spoilers">${toggle}</p>` : ''}`;
}

function entryHtml(entry, data) {
    const chapter = data.byId.get(entry.firstSeen);
    const first = chapter ? `<a href="${chapterUrl(chapter)}">${escapeHtml(chapterTitle(chapter))}</a>` : '';
    const variants = entry.variants.length
        ? `<span class="glossary-variants">${entry.variants.map(([set, value]) => `${escapeHtml(set)}: <span>${escapeHtml(value)}</span>`).join(' · ')}</span>`
        : '';
    return `
        <div class="glossary-entry" id="${escapeHtml(entry.key.replace(/\s+/g, '-'))}">
            <dt>${escapeHtml(entry.title)}</dt>
            <dd>
                ${entry.description ? `<p>${escapeHtml(entry.description)}</p>` : ''}
                ${variants}
                ${first ? `<small class="glossary-first">Уперше: ${first}</small>` : ''}
            </dd>
        </div>`;
}

// The name in every dictionary set other than the one shown as the title
function variants(key) {
    const shown = resolveName(key, 'однина', 'називний');
    const seen = new Set([shown]);
    const result = [];
    for (const set of allSets()) {
        if (set.id === 'custom') continue;
        const value = pickForm(nameValue(key, set.id)) ?? key;
        if (seen.has(value)) continue;
        seen.add(value);
        result.push([set.title, capitalize(value)]);
    }
    return result;
}

function capitalize(text) {
    return text ? text[0].toUpperCase() + text.slice(1) : text;
}

function plural(n, one, few, many) {
    const mod10 = n % 10;
    const mod100 = n % 100;
    if (mod10 === 1 && mod100 !== 11) return one;
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
    return many;
}
