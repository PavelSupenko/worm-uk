#!/usr/bin/env python3
"""Exports a chapter as a script for ElevenLabs Text to Dialogue (Eleven v4).

Usage:
    python3 tools/export_tts.py 1.5                    # write tts/1.5.json
    python3 tools/export_tts.py 1.5 --limit 1500       # smaller chunks
    python3 tools/export_tts.py 1.5 --check tts/1.5.tagged.json

The script is a list of chunks. Each chunk is a request: consecutive whole
paragraphs (first and last number in "paragraphs") whose text stays under
--limit characters, split into "inputs" by voice. Voices are keys of
tts/voices.json; the sender maps them to ElevenLabs voice IDs. Chunks follow
paragraph boundaries so the start time of every chunk in the final audio is
the start of a known paragraph (for text and audio sync).

The default limit (1800) leaves room for audio tags under the API's
2000-character guidance. Audio tags are added by a separate pass
(.claude/skills/tts-tags) into tts/<id>.tagged.json; --check verifies that the
tagged file has the same chunks, voices and words as the current chapter,
only with [tags] added, and that no request grows over 2000 characters.
"""
import json
import re
import sys

from chapterlib import ROOT, chapter_root, find_chapter, read_chapter, voice_runs

MODEL_ID = 'eleven_v4'
DEFAULT_LIMIT = 1800
API_LIMIT = 2000
PARAGRAPH_JOIN = '\n\n'
TAG = re.compile(r'\[[^\[\]]*\]')
SENTENCE_END = re.compile(r'(?<=[.!?…»”])\s+')


def split_long(runs, limit):
    """Splits a paragraph longer than the limit at sentence ends."""
    pieces, current, size = [], [], 0
    for voice, text in runs:
        for sentence in SENTENCE_END.split(text):
            if current and size + len(sentence) + 1 > limit:
                pieces.append(current)
                current, size = [], 0
            if current and current[-1][0] == voice:
                current[-1] = (voice, current[-1][1] + ' ' + sentence)
            else:
                current.append((voice, sentence))
            size += len(sentence) + 1
    if current:
        pieces.append(current)
    return pieces


def build_script(chapter, limit):
    root = chapter_root(read_chapter(chapter))
    if root is None:
        raise SystemExit(f'{chapter["textFile"]}: not in the chapter format, run tools/check_chapters.py')
    chunks, current = [], None

    def add(number, runs):
        nonlocal current
        size = sum(len(text) for _, text in runs)
        if current is None or current['size'] + size + len(PARAGRAPH_JOIN) > limit:
            current = {'paragraphs': [number, number], 'inputs': [], 'size': 0}
            chunks.append(current)
        current['paragraphs'][1] = number
        for i, (voice, text) in enumerate(runs):
            inputs = current['inputs']
            if inputs and inputs[-1]['voice'] == voice:
                # A new paragraph of the same voice continues its input
                inputs[-1]['text'] += (PARAGRAPH_JOIN if i == 0 else ' ') + text
            else:
                inputs.append({'voice': voice, 'text': text})
        current['size'] += size + len(PARAGRAPH_JOIN)

    for number, runs in enumerate(voice_runs(root), start=1):
        if sum(len(text) for _, text in runs) > limit:
            for piece in split_long(runs, limit):
                current = None  # each piece is a request of its own
                add(number, piece)
            current = None
        else:
            add(number, runs)

    for chunk in chunks:
        del chunk['size']
    return {
        'chapter': chapter['id'],
        'model_id': MODEL_ID,
        'narrator': root.attrs['data-narrator'],
        'chunks': chunks,
    }


def normalize(text):
    return re.sub(r'\s+', ' ', TAG.sub(' ', text)).strip()


def check(script, tagged_path):
    tagged = json.loads(open(tagged_path, encoding='utf-8').read())
    problems = []
    expected, actual = script['chunks'], tagged.get('chunks', [])
    if len(expected) != len(actual):
        problems.append(f'{len(actual)} chunks, the chapter has {len(expected)} (export again and re-tag?)')
    for n, (want, got) in enumerate(zip(expected, actual), start=1):
        if want['paragraphs'] != got.get('paragraphs'):
            problems.append(f'chunk {n}: paragraphs {got.get("paragraphs")}, expected {want["paragraphs"]}')
        if [i['voice'] for i in want['inputs']] != [i.get('voice') for i in got.get('inputs', [])]:
            problems.append(f'chunk {n}: voices differ from the chapter')
            continue
        total = sum(len(i['text']) for i in got['inputs'])
        if total > API_LIMIT:
            problems.append(f'chunk {n}: {total} characters with tags, over {API_LIMIT}')
        for m, (w, g) in enumerate(zip(want['inputs'], got['inputs']), start=1):
            a, b = normalize(w['text']), normalize(g['text'])
            if a != b:
                at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                problems.append(f'chunk {n}, input {m} ({w["voice"]}): text changed near '
                                f'"…{a[max(0, at - 30):at + 30]}…" → "…{b[max(0, at - 30):at + 30]}…"')
    tags = sum(len(TAG.findall(i.get('text', ''))) for c in actual for i in c.get('inputs', []))
    for problem in problems:
        print(f'error: {problem}')
    print(f'{tagged_path}: {len(actual)} chunks, {tags} tags, {len(problems)} problems')
    return 1 if problems else 0


def main():
    args = sys.argv[1:]
    limit = int(args[args.index('--limit') + 1]) if '--limit' in args else DEFAULT_LIMIT
    positional = [a for i, a in enumerate(args) if not a.startswith('--') and (i == 0 or args[i - 1] not in ('--limit', '--check'))]
    if len(positional) != 1:
        raise SystemExit(__doc__)
    chapter = find_chapter(positional[0])
    script = build_script(chapter, limit)
    if '--check' in args:
        return check(script, args[args.index('--check') + 1])
    out = ROOT / 'tts' / f'{chapter["id"]}.json'
    out.write_text(json.dumps(script, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    sizes = [sum(len(i['text']) for i in c['inputs']) for c in script['chunks']]
    voices = sorted({i['voice'] for c in script['chunks'] for i in c['inputs']})
    print(f'{out.relative_to(ROOT)}: {len(sizes)} chunks (largest {max(sizes)} characters), voices {", ".join(voices)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
