// Loading of the chapter list and helpers for naming and linking chapters.
import { versioned } from './version.js';

export async function fetchJSON(url) {
    const response = await fetch(versioned(url));
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return response.json();
}

export async function fetchText(url) {
    const response = await fetch(versioned(url));
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return response.text();
}

let chaptersPromise = null;

// Returns { arcs, chapters, byId }. Each chapter gets links to its arc and to
// its neighbours (prev/next) across arc boundaries.
export function loadChapters() {
    chaptersPromise ??= fetchJSON('assets/chapters.json').then(arcs => {
        const chapters = [];
        for (const arc of arcs) {
            for (const chapter of arc.chapters) {
                chapter.arc = arc;
                chapters.push(chapter);
            }
        }
        chapters.forEach((chapter, i) => {
            chapter.prev = chapters[i - 1] ?? null;
            chapter.next = chapters[i + 1] ?? null;
        });
        return { arcs, chapters, byId: new Map(chapters.map(c => [c.id, c])) };
    });
    return chaptersPromise;
}

const isInterlude = chapter => chapter.id.endsWith('.x');

// Short label for lists: "1.5" or "Інтерлюдія"
export function chapterLabel(chapter) {
    return chapter.title ?? (isInterlude(chapter) ? 'Інтерлюдія' : chapter.id);
}

// Full name: "Визрівання 1.5" or "Інтерлюдія 1"
export function chapterTitle(chapter) {
    if (chapter.title) return chapter.title;
    if (isInterlude(chapter)) return `Інтерлюдія ${chapter.arc.id}`;
    return `${chapter.arc.title} ${chapter.id}`;
}

export function chapterUrl(chapter) {
    return `chapter_template.html?ch=${encodeURIComponent(chapter.id)}`;
}

export function isDraft(chapter) {
    return chapter.status === 'draft';
}
