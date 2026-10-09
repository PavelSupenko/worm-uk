#!/usr/bin/env python3
"""Checks chapter markup against assets/chapters.json, assets/names.json and
tts/voices.json.

Usage:
    python3 tools/check_chapters.py          # report problems, exit 1 on errors
    python3 tools/check_chapters.py --fix    # also rewrite firstSeen in names.json

Errors (must be fixed):
  - files listed in chapters.json are missing
  - a chapter is not one <div data-narrator> with <p> paragraphs, or still uses
    the old reader-name/character-name attributes
  - a voice (data-narrator, data-voice) is missing from tts/voices.json
  - a data-name key is missing from names.json, or data-form/data-case is invalid
  - the text inside a data-name span differs from its localized form; the
    voiceover is generated from this text, so it has to be exact
  - a data-name span contains nested tags (replacement would drop them)
  - data-character wraps a form of a name from names.json (use data-name)
  - names.json entries with incomplete declension tables or a wrong firstSeen
Warnings:
  - a capitalized name form appears in the text without any name markup
  - an attribution ("— сказала вона —") sits inside a data-voice span
  - a names.json entry is not used in any chapter
"""
import re
import sys

from chapterlib import (CASES, FORMS, NAMES_FILE, ROOT, VOICES_FILE, Element, all_forms,
                        chapter_root, dump_names, load_chapters, load_json, pick, read_chapter)

SETS = ('localized', 'translit', 'original')
WORD = r"[\w'’ʼ-]"
# A quote that closes, a dash, then narration (and maybe a reopening quote): an attribution
ATTRIBUTION = re.compile(r'[”"]\s*—\s*[^“"”]+?—\s*[“"]|[”"]\s*—\s*[^“"”]+$')
INLINE_TAGS = {'span', 'i', 'em', 'b', 'strong', 'br'}


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


def plain_texts(node, out):
    """Text nodes outside of data-name/data-character spans: (text, line)."""
    for child in node.children:
        if isinstance(child, str):
            out.append((child, node.line))
        elif 'data-name' not in child.attrs and 'data-character' not in child.attrs:
            plain_texts(child, out)
    return out


def check_chapter(chapter, names, voices, errors, warnings, first_seen):
    rel = chapter['textFile']
    fragment = read_chapter(chapter)
    root = chapter_root(fragment)
    if root is None:
        errors.append(f'{rel}: the file must be a single <div data-narrator="..."> element')
        return 0
    if root.attrs['data-narrator'] not in voices:
        errors.append(f'{rel}: narrator "{root.attrs["data-narrator"]}" is not in tts/voices.json')
    stray = [c for c in root.children if isinstance(c, str) and c.strip()]
    if stray:
        errors.append(f'{rel}: text outside of <p> paragraphs')

    spans = 0
    for paragraph in root.elements():
        if paragraph.tag != 'p':
            errors.append(f'{rel}:{paragraph.line}: <{paragraph.tag}> directly in the chapter, expected <p>')
        for element in [paragraph, *paragraph.iter()]:
            where = f'{rel}:{element.line}'
            if element is not paragraph and element.tag not in INLINE_TAGS:
                errors.append(f'{where}: unexpected <{element.tag}> inside a paragraph')
            for legacy in ('reader-name', 'character-name'):
                if legacy in element.attrs:
                    errors.append(f'{where}: old attribute {legacy}, use the new markup (see CLAUDE.md)')
            voice = element.attrs.get('data-voice')
            if voice is not None and voice not in voices:
                errors.append(f'{where}: voice "{voice}" is not in tts/voices.json')
            if voice is not None and ATTRIBUTION.search(element.text()):
                warnings.append(f'{where}: narration inside data-voice="{voice}" ("— сказав він" belongs to the narrator)')
            if 'data-name' in element.attrs:
                spans += 1
                check_name(element, where, names, errors, first_seen, chapter['id'])
            if 'data-character' in element.attrs:
                entry = names.get(element.attrs['data-character'])
                text = element.text().strip('"“”')
                if entry and text in all_forms(entry.get('localized')) | all_forms(entry.get('translit')):
                    errors.append(f'{where}: data-character="{element.attrs["data-character"]}" '
                                  f'("{text}") should be a data-name span')
        nested_voices = [e for e in paragraph.iter() if 'data-voice' in e.attrs]
        if 'data-voice' in paragraph.attrs and nested_voices:
            errors.append(f'{rel}:{paragraph.line}: data-voice inside a paragraph that already has one')

    # Capitalized name forms written as plain text
    texts = plain_texts(root, [])
    for key, entry in names.items():
        forms = all_forms(entry.get('localized')) | all_forms(entry.get('translit'))
        for form_text in sorted(f for f in forms if f[:1].isupper()):
            pattern = re.compile(rf'(?<!{WORD}){re.escape(form_text)}(?!{WORD})')
            for text, line in texts:
                if pattern.search(text):
                    warnings.append(f'{rel}:{line}: "{form_text}" ({key}) is not marked up '
                                    f'(python3 tools/markup_names.py {chapter["id"]})')
    return spans


def check_name(element, where, names, errors, first_seen, chapter_id):
    key = element.attrs['data-name']
    form = element.attrs.get('data-form', 'однина')
    name_case = element.attrs.get('data-case', 'називний')
    text = element.text()
    if element.elements():
        errors.append(f'{where}: {key}: tags inside a data-name span')
    entry = names.get(key)
    if entry is None:
        errors.append(f'{where}: {key} is not in names.json')
        return
    first_seen.setdefault(key, chapter_id)
    if form not in FORMS:
        errors.append(f'{where}: {key}: invalid data-form "{form}"')
    elif name_case not in CASES:
        errors.append(f'{where}: {key}: invalid data-case "{name_case}"')
    else:
        expected = pick(entry.get('localized'), form, name_case)
        if expected and text not in (expected, expected[:1].upper() + expected[1:]):
            errors.append(f'{where}: {key} ({form}, {name_case}): text "{text}", localized form is "{expected}"')


def main():
    fix = '--fix' in sys.argv[1:]
    errors, warnings = [], []
    names_data = load_json(NAMES_FILE)
    names = names_data['names']
    voices = load_json(VOICES_FILE)
    categories = {c['id'] for c in names_data.get('categories', [])}

    for key, entry in names.items():
        if entry.get('category') not in categories:
            errors.append(f'names.json: {key}: unknown category "{entry.get("category")}"')
        if 'localized' not in entry:
            errors.append(f'names.json: {key}: missing "localized"')
        for set_id in SETS:
            if set_id in entry:
                for problem in value_problems(entry[set_id], complete=set_id == 'localized'):
                    errors.append(f'names.json: {key}.{set_id}: {problem}')

    chapters = load_chapters()
    first_seen, spans, seen_ids = {}, 0, set()
    for chapter in chapters:
        cid = chapter['id']
        if cid in seen_ids:
            errors.append(f'chapters.json: duplicate chapter id {cid}')
        seen_ids.add(cid)
        if chapter.get('status') not in (None, 'draft'):
            errors.append(f'chapters.json: {cid}: unknown status "{chapter["status"]}"')
        for field in ('textFile', 'audioFile'):
            value = chapter.get(field)
            # Published voiceovers live in Cloudflare R2 (tools/voice_chapter.py --publish)
            if value and not value.startswith('https://') and not (ROOT / value).is_file():
                errors.append(f'chapters.json: {cid}: {field} not found: {value}')
        if (ROOT / chapter.get('textFile', '')).is_file():
            spans += check_chapter(chapter, names, voices, errors, warnings, first_seen)

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
    print(f'{len(chapters)} chapters, {spans} name spans, {len(errors)} errors, {len(warnings)} warnings')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
