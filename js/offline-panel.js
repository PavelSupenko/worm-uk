// "Читання без інтернету" in the settings: saving every chapter's text at
// once and the list of downloaded voiceovers.
import { chapterTitle, chapterUrl, loadChapters } from './data.js';
import { formatSize, listSavedAudio, offlineSupported, removeAudio, savePages, storageUsage } from './offline.js';
import { escapeHtml, icon } from './ui.js';

export function offlineSection() {
    if (!offlineSupported) return '';
    return `
        <section class="settings-section" data-offline-section>
            <h3 class="settings-label">Читання без інтернету</h3>
            <p class="settings-hint">Відкриті глави зберігаються самі. Озвучку можна завантажити на сторінці глави.</p>
            <button class="button button--small button--ghost" data-save-texts>${icon('download')}Зберегти текст усіх глав</button>
            <p class="settings-hint offline-status" data-offline-status></p>
            <ul class="offline-list" data-offline-list></ul>
        </section>`;
}

export function initOfflineSection(root) {
    const section = root.querySelector('[data-offline-section]');
    if (!section) return () => {};
    const status = section.querySelector('[data-offline-status]');
    const list = section.querySelector('[data-offline-list]');

    const render = async () => {
        const [data, saved, usage] = await Promise.all([loadChapters(), listSavedAudio(), storageUsage()]);
        const byAudio = new Map(data.chapters.filter(c => c.audioFile).map(c => [c.audioFile, c]));
        list.innerHTML = saved.map(({ url, size }) => {
            const chapter = byAudio.get(url);
            const title = chapter ? chapterTitle(chapter) : 'Стара версія озвучки';
            return `
                <li class="offline-item">
                    ${icon('headphones')}
                    <span class="offline-item-title">${escapeHtml(title)}</span>
                    <small>${formatSize(size)}</small>
                    <button class="icon-button" data-remove-audio="${escapeHtml(url)}" aria-label="Видалити озвучку: ${escapeHtml(title)}">${icon('trash')}</button>
                </li>`;
        }).join('');
        if (usage !== null && !status.dataset.busy) status.textContent = `Зайнято на пристрої: ${formatSize(usage)}`;
    };

    section.addEventListener('click', async event => {
        const remove = event.target.closest('[data-remove-audio]');
        if (remove) {
            await removeAudio(remove.dataset.removeAudio);
            render();
        }
        if (event.target.closest('[data-save-texts]')) {
            status.dataset.busy = 'true';
            status.textContent = 'Зберігаю…';
            try {
                const { chapters } = await loadChapters();
                const urls = ['./', ...chapters.map(chapterUrl), ...chapters.filter(c => c.audioFile).map(c => `assets/timings/${c.id}.json`)];
                await savePages(urls);
                status.textContent = `Збережено глав: ${chapters.length}.`;
            } catch (err) {
                console.error(err);
                status.textContent = 'Не вдалося зберегти. Перевірте з’єднання.';
            }
            delete status.dataset.busy;
        }
    });
    return () => render().catch(err => console.error(err));
}
