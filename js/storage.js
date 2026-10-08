// localStorage wrapper. Storage can be unavailable (private mode, blocked site
// data), so every access is guarded and the site keeps working without it.
const PREFIX = 'worm-uk:';

export function load(key, fallback) {
    try {
        const raw = localStorage.getItem(PREFIX + key);
        return raw === null ? fallback : JSON.parse(raw);
    } catch {
        return fallback;
    }
}

export function save(key, value) {
    try {
        localStorage.setItem(PREFIX + key, JSON.stringify(value));
    } catch {
        // Nothing to do: the setting just won't survive a reload
    }
}
