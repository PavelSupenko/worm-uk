// Offline reading: registers the service worker (sw.js) and manages what is
// kept on the device. Pages are cached by the service worker as they are
// opened; voiceovers are downloaded only on request and played from a blob,
// so seeking works without the network.
import { VERSION } from './version.js';

const PAGES = 'worm-pages';
const AUDIO = 'worm-audio';

export const offlineSupported = 'serviceWorker' in navigator && 'caches' in window;

// Locally (VERSION 'dev') the files change all the time, so nothing is cached
export function registerServiceWorker() {
    if (!offlineSupported || VERSION === 'dev') return;
    const register = () => navigator.serviceWorker.register('sw.js').catch(err => console.error('Service worker:', err));
    if (document.readyState === 'complete') register();
    else window.addEventListener('load', register, { once: true });
}

// Must match cacheKey() in sw.js
function cacheKey(url) {
    const parsed = new URL(url, document.baseURI);
    parsed.searchParams.delete('v');
    if (parsed.pathname.endsWith('/')) parsed.pathname += 'index.html';
    parsed.hash = '';
    return parsed.href;
}

// Puts pages and data files into the page cache, as if they had been opened
export async function savePages(urls) {
    const cache = await caches.open(PAGES);
    await Promise.all(urls.map(async url => {
        const response = await fetch(url, { cache: 'no-cache' });
        if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
        await cache.put(cacheKey(url), response);
    }));
}

export async function isAudioSaved(url) {
    if (!offlineSupported) return false;
    const cache = await caches.open(AUDIO);
    return Boolean(await cache.match(url));
}

// A blob: URL of the saved voiceover, or null when it isn't saved
export async function savedAudioUrl(url) {
    if (!offlineSupported) return null;
    const cache = await caches.open(AUDIO);
    const response = await cache.match(url);
    return response ? URL.createObjectURL(await response.blob()) : null;
}

// Downloads a voiceover; onProgress gets a fraction from 0 to 1
export async function saveAudio(url, onProgress = () => {}) {
    const response = await fetch(url, { mode: 'cors' });
    if (!response.ok || !response.body) throw new Error(`${url}: HTTP ${response.status}`);
    const total = Number(response.headers.get('Content-Length')) || 0;
    const reader = response.body.getReader();
    const parts = [];
    let loaded = 0;
    for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        parts.push(value);
        loaded += value.length;
        if (total) onProgress(loaded / total);
    }
    const blob = new Blob(parts, { type: 'audio/mpeg' });
    const cache = await caches.open(AUDIO);
    await cache.put(url, new Response(blob, {
        headers: { 'Content-Type': 'audio/mpeg', 'Content-Length': String(blob.size) }
    }));
    // Ask the browser not to evict downloads when space runs low
    navigator.storage?.persist?.().catch(() => {});
}

export async function removeAudio(url) {
    const cache = await caches.open(AUDIO);
    await cache.delete(url);
}

// [{ url, size }] of every saved voiceover
export async function listSavedAudio() {
    if (!offlineSupported) return [];
    const cache = await caches.open(AUDIO);
    const requests = await cache.keys();
    return Promise.all(requests.map(async request => {
        const response = await cache.match(request);
        return { url: request.url, size: Number(response.headers.get('Content-Length')) || 0 };
    }));
}

export async function storageUsage() {
    const estimate = await navigator.storage?.estimate?.();
    return estimate?.usage ?? null;
}

export function formatSize(bytes) {
    return `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} МБ`;
}
