// Text and audio sync: highlights the paragraph being read, starts the
// voiceover from a paragraph the reader taps, and shows a compact player while
// the main one is scrolled out of view. Paragraph start times come from
// assets/timings/<id>.json (tools/voice_chapter.py), one per <p> of the chapter.
import { fetchJSON } from './data.js';
import { icon } from './ui.js';

// A paragraph counts as started a little early, the first word is often clipped
const LEAD = 0.15;
// No automatic scrolling for a while after the reader scrolled themselves
const USER_SCROLL_PAUSE = 4000;

export async function initAudioSync({ audio, box, article, timingsUrl }) {
    const player = miniPlayer(audio, box);
    let starts = null;
    try {
        starts = (await fetchJSON(timingsUrl)).paragraphs;
    } catch (err) {
        console.warn('Без синхронізації тексту й аудіо:', err);
        return;
    }
    const paragraphs = [...article.querySelectorAll('p')];
    if (paragraphs.length !== starts.length) {
        console.warn(`Без синхронізації: ${paragraphs.length} абзаців, ${starts.length} таймінгів`);
        return;
    }

    box.querySelector('[data-sync-hint]')?.removeAttribute('hidden');
    let current = -1;
    let lastUserScroll = 0;
    const markUserScroll = () => { lastUserScroll = Date.now(); };
    ['wheel', 'touchmove', 'keydown'].forEach(type => window.addEventListener(type, markUserScroll, { passive: true }));

    const indexAt = time => {
        let found = -1;
        for (let i = 0; i < starts.length && starts[i] <= time + LEAD; i++) found = i;
        return found;
    };
    const update = () => {
        const index = player.started() ? indexAt(audio.currentTime) : -1;
        if (index === current) return;
        const previous = paragraphs[current];
        const following = previous && !audio.paused && isOnScreen(previous) && Date.now() - lastUserScroll > USER_SCROLL_PAUSE;
        previous?.classList.remove('is-reading');
        current = index;
        const paragraph = paragraphs[current];
        paragraph?.classList.add('is-reading');
        // Turn the page for a reader who follows along, never for one who scrolled away
        if (paragraph && following && !isComfortablyVisible(paragraph)) scrollToParagraph(paragraph);
    };
    ['timeupdate', 'seeked', 'play', 'ended', 'loadedmetadata'].forEach(type => audio.addEventListener(type, update));
    update();

    player.onLocate(() => {
        const paragraph = paragraphs[current];
        if (paragraph) scrollToParagraph(paragraph);
        else box.scrollIntoView({ behavior: smoothness(), block: 'center' });
    });

    // "Слухати звідси": a tap on a paragraph offers to play from its start
    const picker = document.createElement('button');
    picker.className = 'button button--small listen-here';
    picker.hidden = true;
    picker.innerHTML = `${icon('play')}Слухати звідси`;
    article.append(picker);
    let picked = null;
    const hidePicker = () => {
        picker.hidden = true;
        picked?.classList.remove('is-picked');
        picked = null;
    };
    article.addEventListener('click', event => {
        if (event.target.closest('.listen-here, a, button, [role="button"]')) return;
        if (document.getSelection().toString().trim()) return; // selecting text for a typo report
        const paragraph = event.target.closest('p');
        if (!paragraph || paragraph === picked) return hidePicker();
        hidePicker();
        picked = paragraph;
        picked.classList.add('is-picked');
        picker.hidden = false;
        picker.style.top = `${Math.max(0, paragraph.offsetTop - picker.offsetHeight - 6)}px`;
    });
    picker.addEventListener('click', () => {
        const index = paragraphs.indexOf(picked);
        hidePicker();
        if (index < 0) return;
        audio.currentTime = starts[index];
        audio.play();
    });
    document.addEventListener('click', event => {
        if (picked && !article.contains(event.target)) hidePicker();
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') hidePicker();
    });
}

// Fixed player at the bottom of the screen, shown once listening has started
// and while the main player is scrolled away
function miniPlayer(audio, box) {
    const bar = document.createElement('div');
    bar.className = 'mini-player';
    bar.hidden = true;
    bar.setAttribute('role', 'region');
    bar.setAttribute('aria-label', 'Озвучка');
    bar.innerHTML = `
        <button class="icon-button" data-toggle aria-label="Відтворити">${icon('play')}</button>
        <span class="mini-player-time" data-time></span>
        <button class="icon-button" data-locate aria-label="До абзацу, що звучить" title="До абзацу, що звучить">${icon('locate')}</button>
        <span class="mini-player-progress" data-progress></span>`;
    document.body.append(bar);
    const toggle = bar.querySelector('[data-toggle]');
    const time = bar.querySelector('[data-time]');
    const progress = bar.querySelector('[data-progress]');

    let started = audio.currentTime > 0;
    let boxVisible = true;
    const render = () => {
        const visible = started && !boxVisible;
        bar.hidden = !visible;
        document.body.classList.toggle('has-mini-player', visible);
        const playing = !audio.paused;
        toggle.innerHTML = icon(playing ? 'pause' : 'play');
        toggle.setAttribute('aria-label', playing ? 'Пауза' : 'Відтворити');
        const duration = audio.duration || 0;
        time.textContent = duration ? `${clock(audio.currentTime)} / ${clock(duration)}` : clock(audio.currentTime);
        progress.style.width = duration ? `${(audio.currentTime / duration) * 100}%` : '0';
    };
    audio.addEventListener('play', () => { started = true; render(); });
    audio.addEventListener('loadedmetadata', () => { started ||= audio.currentTime > 0; render(); });
    audio.addEventListener('ended', () => { started = false; render(); });
    // A seek (from a paragraph or the native player) counts as starting to listen
    audio.addEventListener('seeked', () => { started ||= audio.currentTime > 0; render(); });
    ['pause', 'timeupdate'].forEach(type => audio.addEventListener(type, render));
    toggle.addEventListener('click', () => (audio.paused ? audio.play() : audio.pause()));
    new IntersectionObserver(([entry]) => {
        boxVisible = entry.isIntersecting;
        render();
    }).observe(box);

    let locate = () => box.scrollIntoView({ behavior: smoothness(), block: 'center' });
    bar.querySelector('[data-locate]').addEventListener('click', () => locate());
    return {
        started: () => started,
        onLocate: handler => { locate = handler; }
    };
}

function clock(seconds) {
    const total = Math.floor(seconds || 0);
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

function smoothness() {
    return matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
}

function isOnScreen(element) {
    const rect = element.getBoundingClientRect();
    return rect.bottom > 0 && rect.top < window.innerHeight;
}

// The start of the paragraph is in the upper part of the screen
function isComfortablyVisible(element) {
    const top = element.getBoundingClientRect().top;
    return top >= 0 && top < window.innerHeight * 0.75;
}

function scrollToParagraph(paragraph) {
    const top = paragraph.getBoundingClientRect().top + window.scrollY - window.innerHeight * 0.2;
    window.scrollTo({ top, behavior: smoothness() });
}
