#!/usr/bin/env python3
"""Checks chapter markup against assets/chapters.json and assets/names.json.

Usage:
    python3 tools/check_chapters.py          # report problems, exit 1 on errors
    python3 tools/check_chapters.py --fix    # also rewrite firstSeen in names.json

Errors (must be fixed):
  - files listed in chapters.json are missing
  - a data-name key is missing from names.json, or data-form/data-case is invalid
  - the text inside a data-name span differs from its localized form; the
    voiceover is generated from this text, so it has to be exact
  - a data-name span contains nested tags (replacement would drop them)
  - character-name wraps a form of a name from names.json (use data-name)
  - names.json entries with incomplete declension tables or a wrong firstSeen
Warnings:
  - a capitalized name form appears in the text without any name markup
  - a names.json entry is not used in any chapter
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS_FILE = ROOT / 'assets' / 'chapters.json'
NAMES_FILE = ROOT / 'assets' / 'names.json'
FORMS = ('однина', 'множина')
CASES = ('називний', 'родовий', 'давальний', 'знахідний', 'орудний', 'місцевий', 'кличний')
SETS = ('localized', 'translit', 'original')
WORD = r"[\w'’ʼ-]"


def pick(value, form, name_case):
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


def value_problems(value, complete):
    """Returns a list of problems with a name value (empty if fine)."""
    if isinstance(value, str):
        return [] if value.strip() else ['empty string']
    if not isinstance(value, dict):
        return ['must be a string or an object']
    problems = [f'unknown number "{k}"' for k in value if k not in FORMS]
    for form in FORMS:
        number = value.get(form)
        if number is None:
            if complete:
                problems.append(f'missing "{form}"')
        elif isinstance(number, dict):
            missing = [c for c in CASES if not str(number.get(c, '')).strip()]
            unknown = [c for c in number if c not in CASES]
            if missing:
                problems.append(f'{form}: missing cases {", ".join(missing)}')
            if unknown:
                problems.append(f'{form}: unknown cases {", ".join(unknown)}')
        elif not isinstance(number, str):
            problems.append(f'{form}: must be a string or a 7-case object')
    return problems


class ChapterParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.data_names = []       # (key, form, case, text, line)
        self.character_names = []  # (key, text, line)
        self.nested = []           # line numbers of tags inside data-name spans
        self.plain = []            # (text, line) outside of any name span
        self.stack = []            # one entry per open <span>: kind or None
        self.current = None        # data-name span being collected

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        line = self.getpos()[0]
        if self.current is not None:
            self.nested.append(line)
        if tag != 'span':
            return
        if 'data-name' in attrs:
            self.current = {'attrs': attrs, 'text': '', 'line': line}
            self.stack.append('data')
        elif 'character-name' in attrs:
            self.character_names.append([attrs['character-name'], '', line])
            self.stack.append('character')
        else:
            self.stack.append(None)

    def handle_endtag(self, tag):
        if tag != 'span' or not self.stack:
            return
        kind = self.stack.pop()
        if kind == 'data' and self.current is not None:
            a = self.current['attrs']
            self.data_names.append((a['data-name'], a.get('data-form', 'однина'),
                                    a.get('data-case', 'називний'), self.current['text'],
                                    self.current['line']))
            self.current = None

    def handle_data(self, data):
        if self.current is not None:
            self.current['text'] += data
        elif 'character' in self.stack:
            self.character_names[-1][1] += data
        else:
            self.plain.append((data, self.getpos()[0]))


def dump_names(data):
    """names.json formatting: one line per case table and per set/category."""
    text = json.dumps(data, ensure_ascii=False, indent=4)
    one_line = lambda m: json.dumps(json.loads(m.group(0)), ensure_ascii=False)
    text = re.sub(r'\{\s+"називний"[^{}]*\}', one_line, text)
    text = re.sub(r'\{\s+"id"[^{}]*\}', one_line, text)
    return text + '\n'


def main():
    fix = '--fix' in sys.argv[1:]
    errors, warnings = [], []
    arcs = json.loads(CHAPTERS_FILE.read_text(encoding='utf-8'))
    names_data = json.loads(NAMES_FILE.read_text(encoding='utf-8'))
    names = names_data['names']
    categories = {c['id'] for c in names_data.get('categories', [])}

    # names.json itself
    for key, entry in names.items():
        if entry.get('category') not in categories:
            errors.append(f'names.json: {key}: unknown category "{entry.get("category")}"')
        if 'localized' not in entry:
            errors.append(f'names.json: {key}: missing "localized"')
        for set_id in SETS:
            if set_id in entry:
                for problem in value_problems(entry[set_id], complete=set_id == 'localized'):
                    errors.append(f'names.json: {key}.{set_id}: {problem}')

    # Chapters, in reading order
    chapter_order, first_seen = [], {}
    span_count = 0
    seen_ids = set()
    for arc in arcs:
        for chapter in arc['chapters']:
            cid = chapter['id']
            if cid in seen_ids:
                errors.append(f'chapters.json: duplicate chapter id {cid}')
            seen_ids.add(cid)
            chapter_order.append(cid)
            for field in ('textFile', 'audioFile'):
                if field in chapter and not (ROOT / chapter[field]).is_file():
                    errors.append(f'chapters.json: {cid}: {field} not found: {chapter[field]}')
            text_path = ROOT / chapter.get('textFile', '')
            if not text_path.is_file():
                continue
            rel = text_path.relative_to(ROOT)
            parser = ChapterParser()
            parser.feed(text_path.read_text(encoding='utf-8'))
            span_count += len(parser.data_names)

            for line in sorted(set(parser.nested)):
                errors.append(f'{rel}:{line}: tag nested inside a data-name span')
            for key, form, name_case, text, line in parser.data_names:
                where = f'{rel}:{line}: {key}'
                entry = names.get(key)
                if entry is None:
                    errors.append(f'{where}: not in names.json')
                    continue
                first_seen.setdefault(key, cid)
                if form not in FORMS:
                    errors.append(f'{where}: invalid data-form "{form}"')
                    continue
                if name_case not in CASES:
                    errors.append(f'{where}: invalid data-case "{name_case}"')
                    continue
                expected = pick(entry.get('localized'), form, name_case)
                if expected and text != expected and text != expected[:1].upper() + expected[1:]:
                    errors.append(f'{where} ({form}, {name_case}): text "{text}", localized form is "{expected}"')
            for key, text, line in parser.character_names:
                # A description such as "маска-череп" may keep character-name
                entry = names.get(key)
                if entry and text.strip('"“”') in all_forms(entry.get('localized')) | all_forms(entry.get('translit')):
                    errors.append(f'{rel}:{line}: character-name="{key}" ("{text}") should be a data-name span')

            # Capitalized name forms written as plain text
            for key, entry in names.items():
                forms = set()
                for set_id in ('localized', 'translit'):
                    forms |= all_forms(entry.get(set_id))
                for form_text in sorted(f for f in forms if f[:1].isupper()):
                    pattern = rf'(?<!{WORD}){re.escape(form_text)}(?!{WORD})'
                    for data, line in parser.plain:
                        if re.search(pattern, data):
                            warnings.append(f'{rel}:{line}: "{form_text}" ({key}) is not marked up')

    # firstSeen
    for key, entry in names.items():
        actual = first_seen.get(key)
        if actual is None:
            warnings.append(f'names.json: {key} is not used in any chapter')
        elif entry.get('firstSeen') != actual:
            if fix:
                entry['firstSeen'] = actual
            else:
                errors.append(f'names.json: {key}: firstSeen is "{entry.get("firstSeen")}", '
                              f'first used in {actual} (run with --fix)')
    if fix:
        NAMES_FILE.write_text(dump_names(names_data), encoding='utf-8')

    for message in warnings:
        print(f'warning: {message}')
    for message in errors:
        print(f'error: {message}')
    print(f'{len(chapter_order)} chapters, {span_count} name spans, '
          f'{len(errors)} errors, {len(warnings)} warnings')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
