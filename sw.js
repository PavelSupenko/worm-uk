// Service worker: keeps the site readable offline. Same-origin requests go to
// the network first and fall back to the cache, so online readers always get
// the current deploy; every response is cached under its URL without the
// deploy's ?v= parameter, so saved pages keep working after later deploys.
// Downloaded voiceovers live in their own cache, managed by js/offline.js.
// tools/build_site.sh stamps VERSION, tools/build_pages.py fills SHELL.
const VERSION = 'dev';
const SHELL = [];
const PAGES = 'worm-pages';
const FONTS = 'worm-fonts';
const AUDIO = 'worm-audio';
// On a bad connection answer from the cache after this long
const NETWORK_TIMEOUT = 4000;

// Must match cacheKey() in js/offline.js
function cacheKey(url) {
    const parsed = new URL(url, self.location.href);
    parsed.searchParams.delete('v');
    if (parsed.pathname.endsWith('/')) parsed.pathname += 'index.html';
    parsed.hash = '';
    return parsed.href;
}

self.addEventListener('install', event => {
    event.waitUntil((async () => {
        const cache = await caches.open(PAGES);
        await Promise.all(SHELL.map(async path => {
            const response = await fetch(path, { cache: 'reload' });
            if (response.ok) await cache.put(cacheKey(path), response);
        }));
        await self.skipWaiting();
    })());
});

self.addEventListener('activate', event => {
    event.waitUntil((async () => {
        const keep = [PAGES, FONTS, AUDIO];
        for (const name of await caches.keys()) {
            if (!keep.includes(name)) await caches.delete(name);
        }
        await self.clients.claim();
    })());
});

self.addEventListener('fetch', event => {
    const { request } = event;
    if (request.method !== 'GET') return;
    const url = new URL(request.url);
    if (url.origin === self.location.origin) {
        event.respondWith(networkFirst(request));
    } else if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') {
        event.respondWith(cacheFirst(request, url.hostname === 'fonts.googleapis.com'));
    }
});

async function networkFirst(request) {
    const cache = await caches.open(PAGES);
    const key = cacheKey(request.url);
    const network = fetch(request).then(response => {
        if (response.ok && response.type === 'basic') cache.put(key, response.clone());
        return response;
    });
    const timeout = new Promise(resolve => setTimeout(resolve, NETWORK_TIMEOUT, null));
    const first = await Promise.race([network.catch(() => null), timeout]);
    if (first) return first;
    const cached = await cache.match(key);
    if (cached) return cached;
    try {
        return await network;
    } catch {
        return request.mode === 'navigate' ? offlinePage() : Response.error();
    }
}

// Font files never change; the stylesheet is refreshed in the background
async function cacheFirst(request, refresh) {
    const cache = await caches.open(FONTS);
    const cached = await cache.match(request);
    const network = fetch(request).then(response => {
        if (response.ok || response.type === 'opaque') cache.put(request, response.clone());
        return response;
    });
    if (cached) {
        if (refresh) network.catch(() => {});
        return cached;
    }
    return network;
}

function offlinePage() {
    const html = `<!DOCTYPE html>
<html lang="uk"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Немає з'єднання — Worm українською</title>
<style>body{margin:0;padding:48px 16px;background:#1c1c1f;color:#ececef;font:18px/1.6 system-ui,sans-serif;text-align:center}a{color:#f3d34a}</style>
</head><body><h1>Немає з'єднання</h1>
<p>Ця сторінка не збережена для читання без інтернету.</p>
<p><a href="./">До змісту</a></p></body></html>`;
    return new Response(html, { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
}
