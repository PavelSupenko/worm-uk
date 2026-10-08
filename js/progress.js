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

export function updateChapterProgress(id, patch) {
    const state = read();
    state.chapters[id] = { ...state.chapters[id], ...patch };
    state.last = id;
    save(KEY, state);
}
