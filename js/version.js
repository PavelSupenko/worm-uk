// The deploy replaces 'dev' with the commit hash (tools/build_site.sh), so data
// and icon URLs change with every release and never come from a stale cache.
export const VERSION = 'dev';

export function versioned(url) {
    if (VERSION === 'dev') return url;
    const [path, hash] = url.split('#');
    const separator = path.includes('?') ? '&' : '?';
    return `${path}${separator}v=${VERSION}${hash ? `#${hash}` : ''}`;
}
