"""Shared helpers for the chapter tools: paths, names.json, a small DOM for
chapter fragments and the canonical chapter file format.

Chapter format (see CLAUDE.md): one <div data-narrator="Voice"> whose children
are <p> paragraphs, one paragraph per line.
"""
import json
import re
from html import escape
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS_FILE = ROOT / 'assets' / 'chapters.json'
NAMES_FILE = ROOT / 'assets' / 'names.json'
VOICES_FILE = ROOT / 'tts' / 'voices.json'
FORMS = ('однина', 'множина')
CASES = ('називний', 'родовий', 'давальний', 'знахідний', 'орудний', 'місцевий', 'кличний')
VOID_TAGS = {'br'}
# Collapse HTML whitespace but keep no-break spaces
SPACES = re.compile(r'[ \t\r\n]+')


# ---------- Data files ----------

def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_chapters():
    """Chapters in reading order, each dict extended with 'arc'."""
    chapters = []
    for arc in load_json(CHAPTERS_FILE):
        for chapter in arc['chapters']:
            chapters.append({**chapter, 'arc': arc})
    return chapters


def find_chapter(ref):
    """Accepts a chapter id ("1.5") or a path to a chapter file, which may not
    be listed in chapters.json yet."""
    for chapter in load_chapters():
        if chapter['id'] == ref or (ROOT / chapter['textFile']).resolve() == Path(ref).resolve():
            return chapter
    if Path(ref).is_file():
        return {'id': Path(ref).stem, 'textFile': str(Path(ref).resolve())}
    raise SystemExit(f'Unknown chapter: {ref}')


def pick(value, form='однина', name_case='називний'):
    """Mirrors pickForm() in js/names.js: a string is indeclinable, an object
    holds per-number strings or 7-case tables."""
    if value is None or isinstance(value, str):
        return value
    number = value.get(form, value.get('однина'))
    if number is None or isinstance(number, str):
        return number
    return number.get(name_case, number.get('називний'))


def all_forms(value):
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    result = set()
    for number in value.values():
        result |= {number} if isinstance(number, str) else set(number.values())
    return result


def dump_names(data):
    """names.json formatting: one line per case table and per set/category."""
    text = json.dumps(data, ensure_ascii=False, indent=4)
    one_line = lambda m: json.dumps(json.loads(m.group(0)), ensure_ascii=False)
    text = re.sub(r'\{\s+"називний"[^{}]*\}', one_line, text)
    text = re.sub(r'\{\s+"id"[^{}]*\}', one_line, text)
    return text + '\n'


# ---------- DOM ----------

class Element:
    def __init__(self, tag, attrs=None, line=0):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children = []
        self.line = line

    def elements(self):
        return [c for c in self.children if isinstance(c, Element)]

    def iter(self):
        """All descendant elements in document order."""
        for child in self.elements():
            yield child
            yield from child.iter()

    def text(self):
        return ''.join(c if isinstance(c, str) else c.text() for c in self.children)


class _FragmentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element('#fragment')
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        element = Element(tag, attrs, self.getpos()[0])
        self.stack[-1].children.append(element)
        if tag not in VOID_TAGS:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Element(tag, attrs, self.getpos()[0]))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_fragment(html):
    parser = _FragmentParser()
    parser.feed(html)
    parser.close()
    return parser.root


def read_chapter(chapter):
    return parse_fragment((ROOT / chapter['textFile']).read_text(encoding='utf-8'))


def chapter_root(fragment):
    """The <div data-narrator> of a chapter, or None for an invalid file."""
    elements = fragment.elements()
    if len(elements) == 1 and elements[0].tag == 'div' and 'data-narrator' in elements[0].attrs:
        return elements[0]
    return None


def _attrs_html(attrs):
    return ''.join(f' {k}' if v is None else f' {k}="{escape(v, quote=True)}"' for k, v in attrs.items())


def to_html(node):
    if isinstance(node, str):
        return escape(node, quote=False)
    if node.tag in VOID_TAGS:
        return f'<{node.tag}{_attrs_html(node.attrs)}>'
    inner = ''.join(to_html(child) for child in node.children)
    return f'<{node.tag}{_attrs_html(node.attrs)}>{inner}</{node.tag}>'


def normalize_paragraph(paragraph):
    """Collapses whitespace inside a paragraph and trims its edges, in place."""
    def walk(node):
        for i, child in enumerate(node.children):
            if isinstance(child, str):
                node.children[i] = SPACES.sub(' ', child)
            else:
                walk(child)
    walk(paragraph)
    for edge, strip in ((0, str.lstrip), (-1, str.rstrip)):
        node = paragraph
        while node.children:
            child = node.children[edge]
            if isinstance(child, str):
                node.children[edge] = strip(child)
                break
            node = child
    paragraph.children = [c for c in paragraph.children if c != '']


def serialize_chapter(root):
    """Canonical chapter file: the narrator div with one paragraph per line."""
    paragraphs = root.elements()
    for paragraph in paragraphs:
        normalize_paragraph(paragraph)
    lines = [f'<div{_attrs_html(root.attrs)}>']
    lines += ['    ' + to_html(p) for p in paragraphs]
    lines.append('</div>')
    return '\n'.join(lines) + '\n'


def write_chapter(chapter, root):
    (ROOT / chapter['textFile']).write_text(serialize_chapter(root), encoding='utf-8')


def voice_runs(root):
    """Per paragraph, the list of (voice, text) runs with whitespace collapsed:
    what the narrator and other voices say, in order."""
    narrator = root.attrs['data-narrator']
    result = []

    def walk(node, voice, runs):
        for child in node.children:
            if isinstance(child, str):
                runs.append([voice, child])
            elif child.tag == 'br':
                runs.append([voice, ' '])
            else:
                walk(child, child.attrs.get('data-voice', voice), runs)

    for paragraph in root.elements():
        runs = []
        walk(paragraph, paragraph.attrs.get('data-voice', narrator), runs)
        result.append(merge_runs(runs))
    return result


def merge_runs(runs):
    """Merges neighbouring runs of one voice; whitespace-only runs between
    two runs of the same voice join them, other whitespace goes to the earlier run."""
    merged = []
    for voice, text in runs:
        if merged and (merged[-1][0] == voice or not text.strip()):
            merged[-1][1] += text
        elif merged and not merged[-1][1].strip():
            merged[-1] = [voice, merged[-1][1] + text]
        else:
            merged.append([voice, text])
    cleaned = []
    for voice, text in merged:
        text = SPACES.sub(' ', text).strip()
        if not text:
            continue
        if cleaned and cleaned[-1][0] == voice:
            cleaned[-1] = (voice, cleaned[-1][1] + ' ' + text)
        else:
            cleaned.append((voice, text))
    return cleaned
