// Table of contents shared by the home page and the reader's drawer.
import { chapterLabel, chapterUrl, isDraft } from './data.js';
import { getProgress } from './progress.js';
import { icon, escapeHtml } from './ui.js';

// Arcs are collapsible groups. The arc containing openChapterId starts
// expanded, or the first arc when there is nothing to open.
export function renderToc(container, data, { currentId = null, openChapterId = currentId } = {}) {
    const progress = getProgress().chapters;
    const openArc = data.byId.get(openChapterId)?.arc ?? data.arcs[0];
    container.innerHTML = data.arcs.map(arc => `
        <details class="toc-arc" ${arc === openArc ? 'open' : ''}>
            <summary>
                <span class="toc-arc-number">Арка ${escapeHtml(arc.id)}</span>
                <span class="toc-arc-title">${escapeHtml(arc.title)}</span>
            </summary>
            <ol class="toc-list">
                ${arc.chapters.map(chapter => chapterItem(chapter, chapter.id === currentId, progress[chapter.id]?.done)).join('')}
            </ol>
        </details>`).join('');
}

function chapterItem(chapter, isCurrent, isDone) {
    const meta = [
        isDraft(chapter) ? '<span class="badge" title="Текст ще не відредаговано">чернетка</span>' : '',
        chapter.audioFile ? metaIcon('headphones', 'Є озвучка') : '',
        isDone ? metaIcon('check', 'Прочитано', 'toc-icon--done') : ''
    ].join('');
    return `
        <li>
            <a class="toc-link" href="${chapterUrl(chapter)}" ${isCurrent ? 'aria-current="page"' : ''}>
                <span class="toc-label">${escapeHtml(chapterLabel(chapter))}</span>
                <span class="toc-meta">${meta}</span>
            </a>
        </li>`;
}

function metaIcon(name, label, extraClass = '') {
    return `<span class="toc-icon ${extraClass}" role="img" aria-label="${label}" title="${label}">${icon(name)}</span>`;
}
