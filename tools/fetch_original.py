#!/usr/bin/env python3
"""Download the original English text of a Worm chapter, for translating it.

    python3 tools/fetch_original.py 1.6              # -> orig/1.6.txt
    python3 tools/fetch_original.py 1.6 --check      # paragraph count of orig/1.6.txt vs the translation in texts/
    python3 tools/fetch_original.py 1.6 --check-draft [PATH]   # a plain-text translation (default orig/1.6.uk.txt) vs the original
    python3 tools/fetch_original.py --list [ARC]     # chapters of the table of contents (one arc, or all)
    python3 tools/fetch_original.py 4.y --url URL    # a chapter the table of contents lists ambiguously

The chapter id is ours ("1.5", interludes "1.x"); the page is found through the
table of contents at parahumans.wordpress.com (label "1.06" -> id "1.6").
Two ids can match several entries (a second interlude in an arc); then --list
shows their addresses and --url picks one.

The output is one numbered paragraph per line, so a translation can be checked
against it paragraph by paragraph: "---" is a scene break, <i> and <b> are the
original's emphasis, "⏎" is a line break inside a paragraph, navigation links
and hidden text are dropped. It goes to orig/, which git ignores: the original
is Wildbow's text and stays out of the repository.
"""
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from chapterlib import ROOT, find_chapter

TOC_URL = 'https://parahumans.wordpress.com/table-of-contents/'
OUT_DIR = ROOT / 'orig'
USER_AGENT = 'Mozilla/5.0 (compatible; worm-uk-translation-tool; +https://github.com/PavelSupenko/worm-uk)'
SCENE_BREAK = '---'
BLOCKS = {'p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
SKIPPED = {'del', 'script', 'style', 'noscript'}
EMPHASIS = {'em': 'i', 'i': 'i', 'strong': 'b', 'b': 'b'}
# Blocks of the page after the story: sharing buttons, related posts
WIDGET_CLASS = re.compile(r'sharedaddy|jp-relatedposts|wpcnt|post-navigation')


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode('utf-8')
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 2:
                raise SystemExit(f'Could not download {url}: {error}')
            time.sleep(2)


def clean(text):
    return re.sub(r'[ \t\r\n\xa0]+', ' ', text).strip()


# ---------- Table of contents ----------

class TocParser(HTMLParser):
    """Collects the links of the chapters: (label, url) in page order."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.href = None
        self.label = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href')
            self.label = ''

    def handle_data(self, data):
        if self.href is not None:
            self.label += data

    def handle_endtag(self, tag):
        if tag == 'a' and self.href is not None:
            self.links.append((clean(self.label), self.href))
            self.href = None


def read_toc():
    """Returns [{'id', 'label', 'url', 'arc'}] for every chapter of the table of
    contents. 'arc' is the English arc name as in the address (arc-2-insinuation
    -> "2.insinuation"), which is also the folder name in texts/."""
    parser = TocParser()
    parser.feed(fetch(TOC_URL))
    entries, seen = [], set()
    for label, url in parser.links:
        match = re.match(r'(\d+)\.(\d+|[a-z])\b', label)
        arc = re.search(r'/arc-(\d+)-([a-z0-9-]+)/', url)
        if not match or not arc or (label, url) in seen:
            continue
        seen.add((label, url))
        number = match.group(2)
        entries.append({
            'id': f'{int(match.group(1))}.{int(number) if number.isdigit() else number}',
            'label': label,
            'url': url,
            'arc': f'{arc.group(1)}.{arc.group(2)}',
        })
    if not entries:
        raise SystemExit('No chapters found in the table of contents: has the page changed?')
    return entries


def find_entry(chapter_id):
    matches = [entry for entry in read_toc() if entry['id'] == chapter_id]
    if not matches:
        raise SystemExit(f'{chapter_id} is not in the table of contents: see --list')
    if len({entry['url'] for entry in matches}) > 1:
        lines = '\n'.join(f"  {entry['label']}  {entry['url']}" for entry in matches)
        raise SystemExit(f'{chapter_id} matches several chapters, pass the one you want with --url:\n{lines}')
    return matches[0]


# ---------- Chapter page ----------

class ChapterParser(HTMLParser):
    """Collects the paragraphs of the first <div class="entry-content">."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.posts = 0
        self.paragraphs = []       # strings, SCENE_BREAK for a break
        self.depth = 0             # div depth inside the content, 0 outside
        self.widget_depth = 0      # div depth inside a widget, 0 outside
        self.skip = 0              # inside <del> and the like
        self.parts = None          # the open paragraph, a list of strings

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'div':
            if self.depth:
                self.depth += 1
                if self.widget_depth:
                    self.widget_depth += 1
                elif WIDGET_CLASS.search(f"{attrs.get('class', '')} {attrs.get('id', '')}"):
                    self.widget_depth = 1
            elif 'entry-content' in (attrs.get('class') or '').split():
                self.posts += 1
                if self.posts == 1:
                    self.depth = 1
            return
        if not self.depth or self.widget_depth:
            return
        if tag in SKIPPED:
            self.skip += 1
        elif tag in BLOCKS:
            self.close_paragraph()
            self.parts = []
        elif tag == 'hr':
            self.close_paragraph()
            self.paragraphs.append(SCENE_BREAK)
        elif self.parts is not None and not self.skip:
            if tag == 'br':
                self.parts.append(' ⏎ ')
            elif tag in EMPHASIS:
                self.parts.append(f'<{EMPHASIS[tag]}>')

    def handle_endtag(self, tag):
        if tag == 'div':
            if self.depth:
                if self.widget_depth:
                    self.widget_depth -= 1
                self.depth -= 1
                if not self.depth:
                    self.close_paragraph()
            return
        if not self.depth or self.widget_depth:
            return
        if tag in SKIPPED:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCKS:
            self.close_paragraph()
        elif self.parts is not None and not self.skip and tag in EMPHASIS:
            self.parts.append(f'</{EMPHASIS[tag]}>')

    def handle_data(self, data):
        if self.depth and not self.widget_depth and not self.skip and self.parts is not None:
            self.parts.append(data)

    def close_paragraph(self):
        if self.parts is None:
            return
        text = tidy(''.join(self.parts))
        self.parts = None
        if is_navigation(text):
            return
        self.paragraphs.append(text or SCENE_BREAK)


def tidy(text):
    text = clean(text)
    text = re.sub(r'<(i|b)>\s*</\1>', '', text)             # empty emphasis
    text = re.sub(r'<(i|b)>(\s+)', r'\2<\1>', text)         # spaces go outside the tags
    text = re.sub(r'(\s+)</(i|b)>', r'</\2>\1', text)
    text = re.sub(r'</(i|b)>(\s*)<\1>', r'\2', text)        # </i> <i> -> one run
    text = re.sub(r'(?:\s*⏎\s*)+$|^(?:\s*⏎\s*)+', '', text)
    return clean(text)


def is_navigation(text):
    return re.fullmatch(r'(Last Chapter)?\s*(Next Chapter)?', text) is not None and bool(text)


def read_chapter(url):
    parser = ChapterParser()
    parser.feed(fetch(url))
    if not parser.posts:
        raise SystemExit(f'No chapter text found at {url}: has the page changed?')
    if parser.posts > 1:
        raise SystemExit(f'{url} holds {parser.posts} posts: pass the address of one post with --url')
    # Scene breaks only between paragraphs, never twice in a row
    result = []
    for paragraph in parser.paragraphs:
        if paragraph == SCENE_BREAK and (not result or result[-1] == SCENE_BREAK):
            continue
        result.append(paragraph)
    while result and result[-1] == SCENE_BREAK:
        result.pop()
    return result


def write_original(chapter_id, url, paragraphs):
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f'{chapter_id}.txt'
    number = 0
    lines = [
        f'# Original of Worm {chapter_id}, {url}',
        '# Local reference for translating, not for the repository (orig/ is ignored by git).',
        '# One numbered line per paragraph; --- is a scene break; <i>/<b> emphasis; ⏎ a line break inside a paragraph.',
    ]
    for paragraph in paragraphs:
        if paragraph == SCENE_BREAK:
            lines.append(SCENE_BREAK)
        else:
            number += 1
            lines.append(f'{number}\t{paragraph}')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path, number


# ---------- Commands ----------

def count_original(chapter_id):
    path = OUT_DIR / f'{chapter_id}.txt'
    if not path.is_file():
        raise SystemExit(f'{path} not found: run fetch_original.py {chapter_id} first')
    return sum(1 for line in path.read_text(encoding='utf-8').splitlines() if re.match(r'\d+\t', line))


def check(chapter_id):
    original = count_original(chapter_id)
    chapter = find_chapter(chapter_id)
    text = (ROOT / chapter['textFile']).read_text(encoding='utf-8')
    translated = len(re.findall(r'<p[ >]', text))
    print(f'{chapter_id}: {original} paragraphs in the original, {translated} in the translation')
    if original != translated:
        print('The counts differ: one original paragraph must be one <p>')
        return 1
    return 0


def read_numbered(path):
    """Reads an original (N<tab>text) or a draft translation (N. text): returns
    ([(number or SCENE_BREAK, text)], problems). Header lines start with #."""
    items, problems = [], []
    for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line == SCENE_BREAK:
            items.append((SCENE_BREAK, ''))
            continue
        match = re.match(r'(\d+)(?:\.|\t)\s*(.*)$', line)
        if match:
            items.append((int(match.group(1)), match.group(2)))
        else:
            problems.append(f'line {line_number}: no paragraph number (a paragraph split in two?)')
    return items, problems


def check_draft(chapter_id, draft=None):
    """Compares a plain-text translation with the original: the same numbers in
    the same order, the same scene breaks, no empty paragraphs, and the same
    number of <i> runs and line breaks in every paragraph."""
    original_path = OUT_DIR / f'{chapter_id}.txt'
    draft_path = Path(draft) if draft else OUT_DIR / f'{chapter_id}.uk.txt'
    for path in (original_path, draft_path):
        if not path.is_file():
            raise SystemExit(f'{path} not found')
    original, _ = read_numbered(original_path)
    translated, problems = read_numbered(draft_path)
    paragraphs = lambda items: sum(1 for key, _ in items if key != SCENE_BREAK)
    print(f'{chapter_id}: {paragraphs(original)} paragraphs in the original, {paragraphs(translated)} in the draft')
    for position, (a, b) in enumerate(zip(original, translated), 1):
        if a[0] != b[0]:
            problems.append(f'item {position}: the original has {a[0]}, the draft has {b[0]} (a paragraph merged, split, lost or numbered wrong)')
            break
        if a[0] == SCENE_BREAK:
            continue
        if not b[1]:
            problems.append(f'paragraph {a[0]}: empty')
        for mark in ('<i>', '⏎'):
            if a[1].count(mark) != b[1].count(mark):
                problems.append(f'paragraph {a[0]}: {a[1].count(mark)} x {mark} in the original, {b[1].count(mark)} in the draft')
    if len(original) != len(translated) and not any(p.startswith('item') for p in problems):
        problems.append(f'{len(original)} items in the original, {len(translated)} in the draft')
    for problem in problems[:20]:
        print(f'  {problem}')
    if len(problems) > 20:
        print(f'  ... and {len(problems) - 20} more')
    print(f'{len(problems)} problems')
    return 1 if problems else 0


def list_toc(arc=None):
    for entry in read_toc():
        if arc is None or entry['id'].split('.')[0] == arc:
            print(f"{entry['id']:7} {entry['label']:50} {entry['arc']:28} {entry['url']}")


def main(args):
    if '-h' in args or '--help' in args or not args:
        print(__doc__)
        return 0
    if args[0] == '--list':
        list_toc(args[1] if len(args) > 1 else None)
        return 0
    chapter_id = args[0]
    if '--check' in args:
        return check(chapter_id)
    if '--check-draft' in args:
        rest = args[args.index('--check-draft') + 1:]
        return check_draft(chapter_id, rest[0] if rest else None)
    if '--url' in args:
        url = args[args.index('--url') + 1]
    else:
        entry = find_entry(chapter_id)
        url = entry['url']
        print(f"{chapter_id}: {entry['label']}, folder texts/{entry['arc']}/")
        time.sleep(1)
    path, count = write_original(chapter_id, url, read_chapter(url))
    print(f'{count} paragraphs -> {path.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
