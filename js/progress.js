// Reading progress: the last opened chapter plus, per chapter, the scroll
// position (fraction of the page), the audio position and a "finished" flag.
import { load, save } from './storage.js';

const KEY = 'progress';
const EMPTY = { last: null, chapters: {} };

// Re-read on every call so two open tabs don't overwrite each other's data
function read() {
    const state = load(KEY, EMPTY);
    return { last: state.last ?? null, chapters: state.chapters ?? {} };
}

export function getProgress() {
    return read();
}

export function getChapterProgress(id) {
    return read().chapters[id] ?? {};
}

// Position in reading order of the furthest chapter the reader has opened
// (0 for new readers). Names and glossary entries from later chapters stay
// hidden so they don't spoil what comes next.
export function furthestOpened(data) {
    const index = new Map(data.chapters.map((chapter, i) => [chapter.id, i]));
    const opened = Object.keys(read().chapters).map(id => index.get(id) ?? -1);
    return Math.max(0, ...opened);
}

export function updateChapterProgress(id, patch) {
    const state = read();
    state.chapters[id] = { ...state.chapters[id], ...patch };
    state.last = id;
    save(KEY, state);
}
