// Entry point of chapter_template.html: loads the chapter named in the URL.
import { loadChapters, fetchText, chapterTitle, chapterLabel, chapterUrl, isDraft } from './data.js';
import { initNamePopover } from './name-popover.js';
import { loadNames, applyNames } from './names.js';
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
// ?ch=1.5; old links use ?major=1&sub=1.5
const chapterId = params.get('ch') ?? params.get('sub');

// The text arrives asynchronously, so the browser can't restore the position itself
history.scrollRestoration = 'manual';

initSettingsPanel($('open-settings'));
setupDrawer($('toc-dialog'), $('open-toc'), () => {
    $('toc-dialog').querySelector('[aria-current="page"]')?.scrollIntoView({ block: 'center' });
});
autoHideTopbar($('topbar'));
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
    renderAudio(chapter);

    let html;
    try {
        [html] = await Promise.all([fetchText(chapter.textFile), namesReady]);
    } catch (err) {
        console.error(err);
        return showError('Не вдалося завантажити текст', 'Спробуйте оновити сторінку.');
    }
    const article = $('chapter-text');
    article.innerHTML = html;
    applyNames(article);
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
        <audio controls preload="metadata" src="${escapeHtml(chapter.audioFile)}"></audio>
        <div class="audio-rates" role="group" aria-label="Швидкість відтворення">
            <span class="audio-rates-label">Швидкість</span>
            ${AUDIO_RATES.map(rate => `<button class="chip chip--small" data-rate="${rate}">${String(rate).replace('.', ',')}×</button>`).join('')}
        </div>`;
    const audio = box.querySelector('audio');

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
