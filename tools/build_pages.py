#!/usr/bin/env python3
"""Pre-renders the published site for search engines and link previews.

The pages in the repository load their content with fetch(), which search
engines index poorly. At deploy time this script writes, into an assembled
site (tools/build_site.sh):

  - <id>.html for every chapter: chapter_template.html with the title, meta
    description, canonical URL, Open Graph tags, JSON-LD, the heading, the
    prev/next links and the chapter text already in place. js/reader.js uses
    the text from the page instead of fetching it.
  - index.html with the same tags and a static table of contents.
  - chapter_template.html replaced by a redirect for old ?ch= / ?sub= links.
  - 404.html, sitemap.xml, and the list of files sw.js caches for offline use.

Usage: python3 tools/build_pages.py <site dir> <base url>
"""
import json
import re
import subprocess
import sys
from html import escape, unescape
from pathlib import Path

from chapterlib import ROOT, load_chapters, load_json

SITE_NAME = 'Worm українською'
DESCRIPTION = ('Український переклад вебсеріалу Worm від Wildbow (John C. McCrae): '
               'глави з текстом і озвучкою, імена в кількох варіантах перекладу.')
ORIGINAL_URL = 'https://parahumans.wordpress.com/'
AUTHOR = {'@type': 'Person', 'name': 'John C. McCrae', 'alternateName': 'Wildbow'}
TRANSLATOR = {'@type': 'Person', 'name': 'Pavlo Supenko'}
OG_IMAGE = 'assets/og-image.png'
DESCRIPTION_LENGTH = 160


def icon(name):
    return f'<svg class="icon" aria-hidden="true"><use href="assets/icons.svg#{name}"></use></svg>'


# ---------- Chapter naming, mirrors js/data.js ----------

def is_interlude(chapter):
    return chapter['id'].endswith('.x')


def chapter_label(chapter):
    return chapter.get('title') or ('Інтерлюдія' if is_interlude(chapter) else chapter['id'])


def chapter_title(chapter):
    if chapter.get('title'):
        return chapter['title']
    if is_interlude(chapter):
        return f'Інтерлюдія {chapter["arc"]["id"]}'
    return f'{chapter["arc"]["title"]} {chapter["id"]}'


def chapter_url(chapter):
    return f'{chapter["id"]}.html'


# ---------- Helpers ----------

def fill(html, pattern, replacement, what):
    """Replaces exactly one match, so a changed template fails the build."""
    result, count = re.subn(pattern, lambda _: replacement, html, flags=re.S)
    if count != 1:
        sys.exit(f'build_pages: expected one {what} in the template, found {count}')
    return result


def plain_text(fragment):
    text = re.sub(r'<[^>]+>', ' ', fragment)
    return re.sub(r'\s+', ' ', unescape(text)).strip().replace(' ,', ',').replace(' .', '.')


def shorten(text, limit=DESCRIPTION_LENGTH):
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(' ', 1)[0].rstrip(',;:—–- ')
    return f'{cut}…'


def json_ld(data):
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    return f'<script type="application/ld+json">{text}</script>'


def head_tags(*, title, description, url, base, og_type='website', extra=''):
    return '\n'.join([
        f'<title>{escape(title)}</title>',
        f'    <meta name="description" content="{escape(description)}">',
        f'    <link rel="canonical" href="{escape(url)}">',
        '    <link rel="apple-touch-icon" href="assets/icon-180.png">',
        f'    <meta property="og:site_name" content="{SITE_NAME}">',
        '    <meta property="og:locale" content="uk_UA">',
        f'    <meta property="og:type" content="{og_type}">',
        f'    <meta property="og:title" content="{escape(title)}">',
        f'    <meta property="og:description" content="{escape(description)}">',
        f'    <meta property="og:url" content="{escape(url)}">',
        f'    <meta property="og:image" content="{base}/{OG_IMAGE}">',
        '    <meta property="og:image:width" content="1200">',
        '    <meta property="og:image:height" content="630">',
        '    <meta name="twitter:card" content="summary_large_image">',
        *([extra] if extra else []),
    ])


def book(base):
    return {
        '@type': 'Book',
        'name': 'Worm',
        'url': f'{base}/',
        'inLanguage': 'uk',
        'author': AUTHOR,
        'translator': TRANSLATOR,
        'translationOfWork': {'@type': 'Book', 'name': 'Worm', 'inLanguage': 'en', 'url': ORIGINAL_URL, 'author': AUTHOR},
    }


def last_modified(*paths):
    """Date of the last commit touching any of the files, or None outside git."""
    try:
        out = subprocess.run(['git', 'log', '-1', '--format=%cs', '--', *paths],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return out or None


def duration(seconds):
    seconds = round(seconds)
    return f'PT{seconds // 60}M{seconds % 60}S'


# ---------- Pages ----------

def nav_html(chapter):
    prev, nxt = chapter['prev'], chapter['next']
    top = (f'<a class="chip" href="{chapter_url(prev)}" rel="prev">{icon("chevron-left")}{escape(chapter_label(prev))}</a>'
           if prev else '<span></span>')
    if nxt:
        top += f'<a class="chip" href="{chapter_url(nxt)}" rel="next">{escape(chapter_label(nxt))}{icon("chevron-right")}</a>'

    def card(target, rel, caption):
        return (f'<a class="nav-card nav-card--{rel}" href="{chapter_url(target)}" rel="{rel}">'
                f'<small>{caption}</small><strong>{escape(chapter_title(target))}</strong></a>')
    bottom = card(prev, 'prev', 'Попередня') if prev else ''
    bottom += card(nxt, 'next', 'Наступна') if nxt else '<p class="nav-end">Це остання перекладена глава. Далі буде!</p>'
    return top, bottom


def chapter_page(template, chapter, base):
    text = (ROOT / chapter['textFile']).read_text(encoding='utf-8')
    paragraphs = re.findall(r'<p\b[^>]*>(.*?)</p>', text, flags=re.S)
    title = chapter_title(chapter)
    full_title = f'{title} — {SITE_NAME}'
    url = f'{base}/{chapter_url(chapter)}'
    description = shorten(plain_text(' '.join(paragraphs[:3]))) if paragraphs else DESCRIPTION

    data = {
        '@context': 'https://schema.org',
        '@type': 'Chapter',
        'name': title,
        'url': url,
        'inLanguage': 'uk',
        'isPartOf': book(base),
        'position': chapter['position'],
    }
    timings = ROOT / 'assets' / 'timings' / f'{chapter["id"]}.json'
    if chapter.get('audioFile'):
        audio = {'@type': 'AudioObject', 'contentUrl': chapter['audioFile'], 'encodingFormat': 'audio/mpeg', 'inLanguage': 'uk'}
        if timings.is_file():
            audio['duration'] = duration(load_json(timings)['duration'])
        data['audio'] = audio
    extra = [f'    <meta property="og:audio" content="{escape(chapter["audioFile"])}">'] if chapter.get('audioFile') else []
    if chapter.get('prev'):
        extra.append(f'    <link rel="prev" href="{chapter_url(chapter["prev"])}">')
    if chapter.get('next'):
        extra.append(f'    <link rel="next" href="{chapter_url(chapter["next"])}">')
    extra.append(f'    {json_ld(data)}')

    html = fill(template, r'<title>.*?</title>',
                head_tags(title=full_title, description=description, url=url, base=base,
                          og_type='article', extra='\n'.join(extra)), 'title')
    html = fill(html, r'<body>', f'<body data-chapter="{escape(chapter["id"])}">', 'body')
    html = fill(html, r'<span class="topbar-title" id="topbar-title"></span>',
                f'<span class="topbar-title" id="topbar-title">{escape(title)}</span>', 'topbar title')
    html = fill(html, r'<p class="chapter-kicker" id="chapter-kicker"></p>',
                f'<p class="chapter-kicker" id="chapter-kicker">Арка {escape(chapter["arc"]["id"])} · {escape(chapter["arc"]["title"])}</p>',
                'kicker')
    html = fill(html, r'<h1 class="chapter-title" id="chapter-title">.*?</h1>',
                f'<h1 class="chapter-title" id="chapter-title">{escape(title)}</h1>', 'title heading')
    if chapter.get('status') == 'draft':
        html = fill(html, r'id="chapter-draft" hidden>', 'id="chapter-draft">', 'draft notice')
    top, bottom = nav_html(chapter)
    html = fill(html, r'<nav class="chapter-nav chapter-nav--top" id="nav-top"[^>]*></nav>',
                f'<nav class="chapter-nav chapter-nav--top" id="nav-top" aria-label="Сусідні глави">{top}</nav>', 'top nav')
    html = fill(html, r'<nav class="chapter-nav chapter-nav--bottom" id="nav-bottom"[^>]*></nav>',
                f'<nav class="chapter-nav chapter-nav--bottom" id="nav-bottom" aria-label="Сусідні глави">{bottom}</nav>', 'bottom nav')
    html = fill(html, r'<article class="chapter-text" id="chapter-text">.*?</article>',
                f'<article class="chapter-text" id="chapter-text" data-prerendered>\n{text.strip()}\n        </article>',
                'chapter text')
    return html


def toc_html(arcs):
    """Static table of contents, the markup js/toc.js renders (without progress marks)."""
    parts = []
    for i, arc in enumerate(arcs):
        items = []
        for chapter in arc['chapters']:
            meta = ''
            if chapter.get('status') == 'draft':
                meta += '<span class="badge" title="Текст ще не відредаговано">чернетка</span>'
            if chapter.get('audioFile'):
                meta += f'<span class="toc-icon" role="img" aria-label="Є озвучка" title="Є озвучка">{icon("headphones")}</span>'
            items.append(f'<li><a class="toc-link" href="{chapter_url(chapter)}">'
                         f'<span class="toc-label">{escape(chapter_label(chapter))}</span>'
                         f'<span class="toc-meta">{meta}</span></a></li>')
        parts.append(f'<details class="toc-arc"{" open" if i == 0 else ""}><summary>'
                     f'<span class="toc-arc-number">Арка {escape(arc["id"])}</span>'
                     f'<span class="toc-arc-title">{escape(arc["title"])}</span></summary>'
                     f'<ol class="toc-list">{"".join(items)}</ol></details>')
    return ''.join(parts)


def index_page(source, arcs, base):
    data = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'WebSite', 'name': SITE_NAME, 'url': f'{base}/', 'inLanguage': 'uk'},
        {**book(base), 'description': DESCRIPTION, 'hasPart': [
            {'@type': 'Chapter', 'name': chapter_title(c), 'url': f'{base}/{chapter_url(c)}'}
            for arc in arcs for c in arc['chapters']]},
    ]}
    html = fill(source, r'<title>.*?</title>\s*<meta name="description"[^>]*>',
                head_tags(title=f'{SITE_NAME} — переклад вебсеріалу Wildbow з озвучкою', description=DESCRIPTION,
                          url=f'{base}/', base=base, extra=f'    {json_ld(data)}'), 'title and description')
    return fill(html, r'<div class="toc toc--grid" id="toc"></div>',
                f'<div class="toc toc--grid" id="toc">{toc_html(arcs)}</div>', 'table of contents')


REDIRECT = '''<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="robots" content="noindex">
    <title>Worm українською</title>
    <script>
        // Old links: chapter_template.html?ch=1.5 or ?major=1&sub=1.5
        var params = new URLSearchParams(location.search);
        var id = params.get('ch') || params.get('sub');
        location.replace(id && /^[\\w.-]+$/.test(id) ? id + '.html' + location.hash : './');
    </script>
</head>
<body>
    <p><a href="./">Worm українською</a></p>
</body>
</html>
'''

NOT_FOUND = '''<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex">
    <base href="{path}/">
    <title>Сторінку не знайдено — Worm українською</title>
    <link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
    <link rel="stylesheet" href="styles.css">
    <script src="js/boot.js"></script>
</head>
<body>
    <main class="page">
        <section class="hero">
            <h1 class="hero-title">404</h1>
            <p class="hero-lead">Такої сторінки немає. Можливо, посилання застаріло.</p>
            <a class="button" href="./">На головну</a>
        </section>
    </main>
</body>
</html>
'''


def sitemap(chapters, base):
    entries = [(f'{base}/', last_modified('assets/chapters.json', 'index.html'))]
    entries += [(f'{base}/{chapter_url(c)}', last_modified(c['textFile'])) for c in chapters]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, date in entries:
        lines.append(f'  <url><loc>{escape(url)}</loc>{f"<lastmod>{date}</lastmod>" if date else ""}</url>')
    lines.append('</urlset>')
    return '\n'.join(lines) + '\n'


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    site = Path(sys.argv[1])
    base = sys.argv[2].rstrip('/')
    arcs = load_json(ROOT / 'assets' / 'chapters.json')
    chapters = load_chapters()
    for i, chapter in enumerate(chapters):
        chapter['position'] = i + 1
        chapter['prev'] = chapters[i - 1] if i else None
        chapter['next'] = chapters[i + 1] if i + 1 < len(chapters) else None
    for arc in arcs:
        arc['chapters'] = [c for c in chapters if c['arc']['id'] == arc['id']]

    template = (ROOT / 'chapter_template.html').read_text(encoding='utf-8')
    for chapter in chapters:
        (site / chapter_url(chapter)).write_text(chapter_page(template, chapter, base), encoding='utf-8')
    index = (ROOT / 'index.html').read_text(encoding='utf-8')
    (site / 'index.html').write_text(index_page(index, arcs, base), encoding='utf-8')
    (site / 'chapter_template.html').write_text(REDIRECT, encoding='utf-8')
    path = re.sub(r'^https?://[^/]+', '', base)
    (site / '404.html').write_text(NOT_FOUND.replace('{path}', path), encoding='utf-8')
    (site / 'sitemap.xml').write_text(sitemap(chapters, base), encoding='utf-8')
    write_shell(site)
    print(f'build_pages: {len(chapters)} chapter pages, index, sitemap')


def write_shell(site):
    """Lists the files every page needs in sw.js, which caches them on install.
    Chapters are cached when opened or saved for offline reading."""
    files = ['./', 'glossary.html', 'styles.css', 'manifest.webmanifest',
             'assets/chapters.json', 'assets/names.json', 'assets/glossary.json',
             'assets/icons.svg', 'assets/favicon.svg', 'assets/icon-192.png']
    files += sorted(f'js/{path.name}' for path in (site / 'js').glob('*.js'))
    missing = [f for f in files if f != './' and not (site / f).is_file()]
    if missing:
        sys.exit(f'build_pages: files for sw.js are missing: {", ".join(missing)}')
    sw = site / 'sw.js'
    sw.write_text(fill(sw.read_text(encoding='utf-8'), r'const SHELL = \[\];',
                       f'const SHELL = {json.dumps(files)};', 'SHELL list in sw.js'), encoding='utf-8')


if __name__ == '__main__':
    main()
