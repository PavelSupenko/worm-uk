// Entry point of chapter_template.html and the pre-rendered chapter pages.
import { initAudioSync } from './audio-sync.js';
import { loadChapters, fetchText, chapterTitle, chapterLabel, chapterUrl, isDraft } from './data.js';
import { initNamePopover } from './name-popover.js';
import { loadNames, applyNames } from './names.js';
import { isAudioSaved, offlineSupported, registerServiceWorker, removeAudio, saveAudio, savedAudioUrl } from './offline.js';
import { getChapterProgress, updateChapterProgress } from './progress.js';
import { initSettingsPanel, getSettings, openSettings, updateSettings } from './settings.js';
import { renderToc } from './toc.js';
import { initTypoReport } from './typo-report.js';
import { icon, escapeHtml, setupDrawer, autoHideTopbar } from './ui.js';

const AUDIO_RATES = [0.75, 1, 1.25, 1.5, 2];
// Scroll fraction from which a chapter counts as read
const DONE_AT = 0.97;

const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
// Pre-rendered pages name their chapter on <body>; the template takes ?ch=1.5
// (old links use ?major=1&sub=1.5)
const chapterId = document.body.dataset.chapter ?? params.get('ch') ?? params.get('sub');
// A pre-rendered page already holds the chapter text
const prerendered = $('chapter-text').hasAttribute('data-prerendered');

// The text arrives asynchronously, so the browser can't restore the position itself
history.scrollRestoration = 'manual';

initSettingsPanel($('open-settings'));
setupDrawer($('toc-dialog'), $('open-toc'), () => {
    $('toc-dialog').querySelector('[aria-current="page"]')?.scrollIntoView({ block: 'center' });
});
autoHideTopbar($('topbar'));
registerServiceWorker();
main();

async function main() {
    // Fetch names in parallel; without them the chapter still shows its inline text
    const namesReady = loadNames().catch(err => console.error('Не вдалося завантажити імена:', err));

    let data;
    try {
        data = await loadChapters();
    } catch (err) {
        console.error(err);
        return showError('Не вдалося завантажити зміст', 'Спробуйте оновити сторінку.');
    }

    const chapter = data.byId.get(chapterId);
    renderToc($('toc-container'), data, { currentId: chapter?.id });
    if (!chapter) return showError('Главу не знайдено', 'Можливо, посилання застаріло. Оберіть главу зі змісту.');

    updateChapterProgress(chapter.id, {}); // remember as the last opened chapter
    renderHeading(chapter);
    renderNav(chapter);
    const audio = renderAudio(chapter);

    const article = $('chapter-text');
    try {
        const [html] = await Promise.all([prerendered ? null : fetchText(chapter.textFile), namesReady]);
        if (html !== null) article.innerHTML = html;
    } catch (err) {
        console.error(err);
        return showError('Не вдалося завантажити текст', 'Спробуйте оновити сторінку.');
    }
    applyNames(article);
    if (audio) initAudioSync({ audio, box: $('audio'), article, timingsUrl: `assets/timings/${chapter.id}.json` });
    initNamePopover(article, {
        onCustomize: key => openSettings({ tab: 'names', nameKey: key })
    });
    initTypoReport(article, $('report-hint'), {
        title: chapterTitle(chapter),
        url: new URL(chapterUrl(chapter), location.href).href
    });

    await document.fonts.ready; // fonts change the page height
    restoreScroll(chapter.id);
    trackScroll(chapter.id);
}

function renderHeading(chapter) {
    const title = chapterTitle(chapter);
    document.title = `${title} — Worm українською`;
    $('topbar-title').textContent = title;
    $('chapter-kicker').textContent = `Арка ${chapter.arc.id} · ${chapter.arc.title}`;
    $('chapter-title').textContent = title;
    $('chapter-draft').hidden = !isDraft(chapter);
}

function renderNav({ prev, next }) {
    $('nav-top').innerHTML = `
        ${prev ? `<a class="chip" href="${chapterUrl(prev)}" rel="prev">${icon('chevron-left')}${escapeHtml(chapterLabel(prev))}</a>` : '<span></span>'}
        ${next ? `<a class="chip" href="${chapterUrl(next)}" rel="next">${escapeHtml(chapterLabel(next))}${icon('chevron-right')}</a>` : ''}`;
    $('nav-bottom').innerHTML = `
        ${prev ? navCard(prev, 'prev', 'Попередня') : ''}
        ${next ? navCard(next, 'next', 'Наступна') : '<p class="nav-end">Це остання перекладена глава. Далі буде!</p>'}`;
}

function navCard(chapter, rel, caption) {
    return `
        <a class="nav-card nav-card--${rel}" href="${chapterUrl(chapter)}" rel="${rel}">
            <small>${caption}</small>
            <strong>${escapeHtml(chapterTitle(chapter))}</strong>
        </a>`;
}

function renderAudio(chapter) {
    const box = $('audio');
    if (!chapter.audioFile) {
        box.innerHTML = `<p class="audio-missing">${icon('headphones')}Озвучка для цієї глави ще готується.</p>`;
        return;
    }
    box.innerHTML = `
        <audio controls preload="metadata"></audio>
        <div class="audio-rates" role="group" aria-label="Швидкість відтворення">
            <span class="audio-rates-label">Швидкість</span>
            ${AUDIO_RATES.map(rate => `<button class="chip chip--small" data-rate="${rate}">${String(rate).replace('.', ',')}×</button>`).join('')}
        </div>
        <div class="audio-offline" data-offline hidden></div>
        <p class="audio-hint" data-sync-hint hidden>Натисніть на абзац, щоб слухати з нього.</p>`;
    const audio = box.querySelector('audio');
    // A voiceover saved for offline listening plays from the device
    savedAudioUrl(chapter.audioFile)
        .catch(() => null)
        .then(url => { audio.src = url ?? chapter.audioFile; });
    renderOffline(box.querySelector('[data-offline]'), chapter);

    // Speed buttons: iOS Safari's native player has no speed control
    const showRate = () => box.querySelectorAll('[data-rate]').forEach(button => {
        button.setAttribute('aria-pressed', String(Number(button.dataset.rate) === audio.playbackRate));
    });
    const setRate = rate => {
        audio.defaultPlaybackRate = rate;
        audio.playbackRate = rate;
    };
    setRate(getSettings().audioRate);
    showRate();
    box.addEventListener('click', event => {
        const button = event.target.closest('[data-rate]');
        if (button) setRate(Number(button.dataset.rate));
    });
    audio.addEventListener('ratechange', () => {
        showRate();
        if (audio.playbackRate !== getSettings().audioRate) updateSettings({ audioRate: audio.playbackRate });
    });

    // Resume where the reader stopped listening
    audio.addEventListener('loadedmetadata', () => {
        const saved = getChapterProgress(chapter.id).audioTime;
        if (saved > 5 && saved < audio.duration - 5) audio.currentTime = saved;
    }, { once: true });
    let lastSaved = 0;
    const saveTime = () => {
        lastSaved = audio.currentTime;
        updateChapterProgress(chapter.id, { audioTime: Math.floor(audio.currentTime) });
    };
    audio.addEventListener('timeupdate', () => {
        if (Math.abs(audio.currentTime - lastSaved) >= 5) saveTime();
    });
    audio.addEventListener('pause', saveTime);
    audio.addEventListener('ended', () => updateChapterProgress(chapter.id, { audioTime: 0 }));

    // Title on the lock screen and in system media controls
    if ('mediaSession' in navigator) {
        navigator.mediaSession.metadata = new MediaMetadata({
            title: chapterTitle(chapter),
            artist: 'Worm — український переклад',
            album: `Арка ${chapter.arc.id}: ${chapter.arc.title}`
        });
    }
    return audio;
}

// "Завантажити": keeps the voiceover on the device for listening offline
async function renderOffline(container, chapter) {
    if (!offlineSupported) return;
    const url = chapter.audioFile;
    const render = async () => {
        const saved = await isAudioSaved(url);
        container.innerHTML = saved
            ? `<span class="audio-offline-state">${icon('check')}Збережено для офлайну</span>
               <button class="link-button" data-remove>Видалити</button>`
            : `<button class="chip chip--small" data-save>${icon('download')}Завантажити для офлайну</button>`;
        container.hidden = false;
    };
    container.addEventListener('click', async event => {
        if (event.target.closest('[data-save]')) {
            container.innerHTML = `<span class="audio-offline-state" data-progress>${icon('download')}Завантаження…</span>`;
            const label = container.querySelector('[data-progress]');
            try {
                await saveAudio(url, fraction => {
                    label.lastChild.textContent = `Завантаження… ${Math.round(fraction * 100)}%`;
                });
            } catch (err) {
                console.error(err);
                container.innerHTML = `<span class="audio-offline-state">Не вдалося завантажити. Спробуйте ще раз.</span>`;
                setTimeout(render, 3000);
                return;
            }
            render();
        } else if (event.target.closest('[data-remove]')) {
            await removeAudio(url);
            render();
        }
    });
    render().catch(err => console.error(err));
}

function scrollMax() {
    return document.documentElement.scrollHeight - window.innerHeight;
}

function restoreScroll(id) {
    const { scroll } = getChapterProgress(id);
    // A finished chapter opens from the top again
    if (scroll > 0.01 && scroll < DONE_AT) window.scrollTo(0, scroll * scrollMax());
}

function trackScroll(id) {
    let timer = null;
    const persist = () => {
        timer = null;
        const max = scrollMax();
        if (max <= 0) return;
        const fraction = Math.min(1, window.scrollY / max);
        const patch = { scroll: Math.round(fraction * 1000) / 1000 };
        if (fraction >= DONE_AT) patch.done = true;
        updateChapterProgress(id, patch);
    };
    window.addEventListener('scroll', () => {
        timer ??= setTimeout(persist, 800);
    }, { passive: true });
    window.addEventListener('pagehide', () => {
        if (timer) {
            clearTimeout(timer);
            persist();
        }
    });
}

function showError(title, message) {
    $('chapter-title').textContent = title;
    $('chapter-kicker').textContent = '';
    $('audio').hidden = true;
    $('chapter-text').innerHTML = `
        <div class="notice notice--error">
            <p>${escapeHtml(message)}</p>
            <p><a href="index.html">Повернутися до змісту</a></p>
        </div>`;
}
