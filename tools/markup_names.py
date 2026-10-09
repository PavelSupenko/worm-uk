#!/usr/bin/env python3
"""Wraps unmarked names in a chapter with data-name spans.

Usage:
    python3 tools/markup_names.py 1.7            # show what would change
    python3 tools/markup_names.py 1.7 --write    # apply and rewrite the file

Finds capitalized localized or transliterated forms from assets/names.json in
plain text and picks the case from the form itself ("Мороком" is Grue, орудний).
Where one form fits several cases (родовий and знахідний of "Луна"), the
preposition before it decides when it can; such guesses are listed for review.
Forms that stay ambiguous are listed with their context and left unmarked:
add those spans by hand. The span text is always the localized form, so a
transliterated "Ґрю" becomes "Морок" in the right case.
Lowercase terms (кейп, штаб) are never marked automatically.
"""
import re
import sys

from chapterlib import (NAMES_FILE, Element, chapter_root, find_chapter, load_json, pick,
                        read_chapter, write_chapter, FORMS, CASES)

WORD = r"[\w'’ʼ-]"
CONTEXT = 40
# Prepositions that settle родовий vs знахідний ("у"/"в" take both, so they don't count)
GENITIVE_PREPOSITIONS = {
    'до', 'від', 'для', 'без', 'біля', 'з', 'із', 'зі', 'після', 'проти', 'серед', 'навколо',
    'замість', 'крім', 'окрім', 'коло', 'позаду', 'поруч', 'поблизу', 'посеред', 'щодо',
    'задля', 'заради', 'вздовж', 'обабіч', 'край', 'кругом', 'мимо', 'усередині', 'всередині'
}
ACCUSATIVE_PREPOSITIONS = {'про', 'через', 'крізь', 'на', 'за', 'під', 'понад', 'повз', 'попри'}


def build_index(names):
    """Maps every capitalized form to the (key, set, form, case) it can be."""
    index = {}
    for key, entry in names.items():
        for set_id in ('localized', 'translit'):
            value = entry.get(set_id)
            if value is None:
                continue
            for form in FORMS:
                for name_case in CASES:
                    text = pick(value, form, name_case)
                    if text and text[:1].isupper():
                        index.setdefault(text, set()).add((key, set_id, form, name_case))
    return index


def candidates(text, index):
    """(key, [(form, case)...]) for a matched form; localized readings win."""
    readings = index[text]
    keys = {r[0] for r in readings}
    if len(keys) != 1:
        return None, []
    localized = [r for r in readings if r[1] == 'localized']
    chosen = localized or list(readings)
    pairs = sorted({(r[2], r[3]) for r in chosen}, key=lambda p: (FORMS.index(p[0]), CASES.index(p[1])))
    return keys.pop(), pairs


def previous_word(text):
    match = re.search(rf'({WORD}+)\W*$', text)
    return match.group(1).lower() if match else ''


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) != 1:
        raise SystemExit(__doc__)
    write = '--write' in sys.argv
    chapter = find_chapter(args[0])
    names = load_json(NAMES_FILE)['names']
    index = build_index(names)
    root = chapter_root(read_chapter(chapter))
    if root is None:
        raise SystemExit(f'{chapter["textFile"]}: not in the chapter format, run tools/check_chapters.py')
    pattern = re.compile(rf'(?<!{WORD})({"|".join(map(re.escape, sorted(index, key=len, reverse=True)))})(?!{WORD})')
    report = {'marked': [], 'guessed': [], 'ambiguous': []}

    def split_text(text, paragraph_no):
        pieces, last = [], 0
        for match in pattern.finditer(text):
            found = match.group(1)
            key, pairs = candidates(found, index)
            before = text[max(0, match.start() - CONTEXT):match.start()]
            after = text[match.end():match.end() + CONTEXT]
            context = f'…{before}[{found}]{after}…'.replace('\n', ' ')
            note = ''
            if key and len(pairs) > 1 and {c for _, c in pairs} == {'родовий', 'знахідний'} and len({f for f, _ in pairs}) == 1:
                word = previous_word(text[:match.start()])
                wanted = 'родовий' if word in GENITIVE_PREPOSITIONS else 'знахідний' if word in ACCUSATIVE_PREPOSITIONS else None
                if wanted:
                    pairs = [p for p in pairs if p[1] == wanted]
                    note = f'after "{word}"'
            if not key or len(pairs) != 1:
                if not key:
                    options = 'several names'
                elif len(pairs) == len(FORMS) * len(CASES):
                    options = 'indeclinable form, any case'
                else:
                    options = ' | '.join(f'{f} {c}' for f, c in pairs)
                report['ambiguous'].append(f'p{paragraph_no} «{found}» {key or ""}: {options}: {context}')
                continue
            form, name_case = pairs[0]
            span_text = pick(names[key]['localized'], form, name_case)
            if found[:1].isupper():
                span_text = span_text[:1].upper() + span_text[1:]
            attrs = {'data-name': key}
            if form != FORMS[0]:
                attrs['data-form'] = form
            if name_case != CASES[0]:
                attrs['data-case'] = name_case
            span = Element('span', attrs)
            span.children = [span_text]
            pieces += [text[last:match.start()], span]
            last = match.end()
            line = f'p{paragraph_no} «{found}» → {key} {form} {name_case}'
            report['guessed' if note else 'marked'].append(f'{line} ({note}): {context}' if note else line)
        pieces.append(text[last:])
        return [p for p in pieces if p != '']

    def walk(node, paragraph_no):
        children = []
        for child in node.children:
            if isinstance(child, str):
                children += split_text(child, paragraph_no)
            else:
                if 'data-name' not in child.attrs and 'data-character' not in child.attrs:
                    walk(child, paragraph_no)
                children.append(child)
        node.children = children

    for number, paragraph in enumerate(root.elements(), start=1):
        walk(paragraph, number)

    for label, title in (('marked', 'marked'), ('guessed', 'guessed from a preposition, check'),
                         ('ambiguous', 'need a case, mark by hand')):
        if report[label]:
            print(f'{title} ({len(report[label])}):')
            for line in report[label]:
                print(f'  {line}')
    changed = len(report['marked']) + len(report['guessed'])
    if write and changed:
        write_chapter(chapter, root)
        print(f'{chapter["textFile"]}: {changed} names marked. Now run python3 tools/check_chapters.py --fix')
    elif changed:
        print('Dry run, nothing written. Add --write to apply.')
    else:
        print('No unmarked names found.')


if __name__ == '__main__':
    main()
