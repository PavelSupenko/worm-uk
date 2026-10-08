// Entry point of index.html: "continue reading" button and the chapter list.
import { loadChapters, chapterTitle, chapterUrl } from './data.js';
import { getProgress } from './progress.js';
import { initSettingsPanel } from './settings.js';
import { renderToc } from './toc.js';
import { icon, escapeHtml } from './ui.js';

initSettingsPanel(document.getElementById('open-settings'));

loadChapters()
    .then(data => {
        const target = renderContinue(data);
        renderToc(document.getElementById('toc'), data, { openChapterId: target.id });
    })
    .catch(err => {
        console.error(err);
        document.getElementById('toc').innerHTML =
            '<p class="notice notice--error">Не вдалося завантажити зміст. Спробуйте оновити сторінку.</p>';
    });

// Points the main button at the last opened chapter, the next one if that
// chapter is finished, or the first chapter for new readers
function renderContinue(data) {
    const { last, chapters } = getProgress();
    let target = data.byId.get(last);
    let label = 'Продовжити читання';
    if (target && chapters[target.id]?.done && target.next) {
        target = target.next;
        label = 'Наступна глава';
    }
    if (!target) {
        target = data.chapters[0];
        label = 'Почати читати';
    }
    const button = document.getElementById('continue');
    button.href = chapterUrl(target);
    button.innerHTML = `
        ${icon('book')}
        <span class="button-text">
            <span>${label}</span>
            <small>${escapeHtml(chapterTitle(target))}</small>
        </span>`;
    button.hidden = false;
    return target;
}
