#!/usr/bin/env python3
"""Voices a chapter with ElevenLabs Text to Dialogue (Eleven v4) and publishes it.

Usage:
    python3 tools/voice_chapter.py 1.5                  # generate missing chunks, join, write timings
    python3 tools/voice_chapter.py 1.5 --chunks 3-4     # only some chunks (tests, partial work)
    python3 tools/voice_chapter.py 1.5 --retake 3       # generate chunk 3 again
    python3 tools/voice_chapter.py 1.5 --publish        # upload to R2, point chapters.json at it
Options:
    --script PATH     use another tagged script instead of tts/<id>.tagged.json
    --untagged        use the plain export, without audio tags

Every chunk of the script (whole paragraphs, see tools/export_tts.py) is one
Text to Dialogue request: the narrator and the characters in one call, so the
model hears the scene. The end of the previous chunk and the start of the next
one go along as previous_text/future_text to keep the intonation across seams.
The tagged script is checked against the current chapter first, so the audio
always matches the published text. Requests whose content didn't change are
not sent again.

Work files are in tts/audio/<id>/ (not committed): chunk-NN.mp3, manifest.json,
<id>.mp3 (the joined chapter) and timings.json (start time of every paragraph,
estimated within a chunk from its share of the characters).
--publish uploads <id>.mp3 to R2 under a content-hashed name, writes
assets/timings/<id>.json and sets audioFile in assets/chapters.json.
Needs ELEVENLABS_API_KEY (and R2_* for --publish) in the environment, and ffmpeg.
"""
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from chapterlib import CHAPTERS_FILE, ROOT, VOICES_FILE, chapter_root, find_chapter, load_json, read_chapter, voice_runs
from export_tts import DEFAULT_LIMIT, TAG, apply_stress, build_script, check

API = 'https://api.elevenlabs.io/v1/text-to-dialogue'
# Chunks come at a higher bitrate; joining encodes the chapter once to FINAL_BITRATE
OUTPUT_FORMAT = 'mp3_44100_128'
FINAL_BITRATE = '64k'
LANGUAGE = 'uk'
CONTEXT_CHARS = 100  # API limit for previous_text / future_text
CHUNK_PAUSE = 0.4    # seconds of silence between chunks (they end on a paragraph)


def plain(text):
    return ' '.join(TAG.sub(' ', text).split())


def parse_range(value, count):
    numbers = set()
    for part in value.split(','):
        first, _, last = part.partition('-')
        numbers.update(range(int(first), int(last or first) + 1))
    return sorted(n for n in numbers if 1 <= n <= count)


def duration(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def generate(chunk, voice_ids, model_id, previous, following):
    body = {
        'inputs': [{'text': i['text'], 'voice_id': voice_ids[i['voice']]} for i in chunk['inputs']],
        'model_id': model_id,
        'language_code': LANGUAGE,
    }
    if previous:
        body['previous_text'] = previous[-CONTEXT_CHARS:]
    if following:
        body['future_text'] = following[:CONTEXT_CHARS]
    request = urllib.request.Request(f'{API}?output_format={OUTPUT_FORMAT}', data=json.dumps(body).encode(),
                                     method='POST', headers={'xi-api-key': os.environ['ELEVENLABS_API_KEY'].strip(),
                                                             'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return response.read(), response.headers.get('request-id')
    except urllib.error.HTTPError as error:
        raise SystemExit(f'ElevenLabs: HTTP {error.code}\n{error.read().decode(errors="replace")[:500]}')


def join(work, chapter_id, count):
    """Decodes the chunks, puts a short pause between them and encodes the
    chapter once (copying MP3 frames leaves glitches at the seams). Returns the
    chunk start times."""
    chunks = [work / f'chunk-{n:02}.mp3' for n in range(1, count + 1)]
    inputs, graph = [], []
    for i, chunk in enumerate(chunks):
        inputs += ['-i', str(chunk)]
        # Mono 44.1 kHz for every part, a pause padded after all but the last
        pad = f',apad=pad_dur={CHUNK_PAUSE}' if i < count - 1 else ''
        graph.append(f'[{i}:a]aformat=sample_rates=44100:channel_layouts=mono{pad}[a{i}]')
    graph.append(''.join(f'[a{i}]' for i in range(count)) + f'concat=n={count}:v=0:a=1[out]')
    out = work / f'{chapter_id}.mp3'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', *inputs, '-filter_complex', ';'.join(graph), '-map', '[out]',
                    '-c:a', 'libmp3lame', '-b:a', FINAL_BITRATE, str(out)], check=True)
    starts, position = [], 0.0
    for chunk in chunks:
        starts.append(position)
        position += duration(chunk) + CHUNK_PAUSE
    return out, starts


def paragraph_timings(chapter, script, starts, work):
    """Start of every paragraph: the chunk start plus its share of the chunk's characters."""
    lengths = [sum(len(text) for _, text in runs) for runs in voice_runs(chapter_root(read_chapter(chapter)))]
    times = [None] * len(lengths)
    for chunk, start, n in zip(script['chunks'], starts, range(1, len(starts) + 1)):
        first, last = chunk['paragraphs']
        chunk_length = duration(work / f'chunk-{n:02}.mp3')
        total = sum(lengths[p - 1] for p in range(first, last + 1)) or 1
        before = 0
        for p in range(first, last + 1):
            if times[p - 1] is None:
                times[p - 1] = round(start + chunk_length * before / total, 1)
            before += lengths[p - 1]
    return times


def publish(chapter, work):
    sys.path.insert(0, str(Path(__file__).parent))
    import r2

    audio = work / f'{chapter["id"]}.mp3'
    timings = work / 'timings.json'
    if not audio.is_file() or not timings.is_file():
        raise SystemExit(f'Nothing to publish: generate the whole chapter first ({audio} is missing)')
    data = audio.read_bytes()
    folder = Path(chapter['textFile']).parent.name  # e.g. 1.gestation
    key = f'{folder}/{chapter["id"]}-{hashlib.sha256(data).hexdigest()[:8]}.mp3'
    url = r2.put_file(r2.config(), key, data, 'audio/mpeg')

    target = ROOT / 'assets' / 'timings' / f'{chapter["id"]}.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(timings.read_text(), encoding='utf-8')

    arcs = load_json(CHAPTERS_FILE)
    for arc in arcs:
        for entry in arc['chapters']:
            if entry['id'] == chapter['id']:
                entry['audioFile'] = url
    CHAPTERS_FILE.write_text(json.dumps(arcs, ensure_ascii=False, indent=4) + '\n', encoding='utf-8')
    print(f'published {url}\nupdated assets/chapters.json and {target.relative_to(ROOT)}; '
          f'run tools/check_chapters.py, then commit and push')


def main():
    args = sys.argv[1:]
    option = lambda name: args[args.index(name) + 1] if name in args else None
    positional = [a for i, a in enumerate(args)
                  if not a.startswith('--') and (i == 0 or args[i - 1] not in ('--chunks', '--retake', '--script'))]
    if len(positional) != 1:
        raise SystemExit(__doc__)
    chapter = find_chapter(positional[0])
    work = ROOT / 'tts' / 'audio' / chapter['id']
    if '--publish' in args:
        return publish(chapter, work)

    if '--untagged' in args:
        script = build_script(chapter, DEFAULT_LIMIT)
    else:
        path = Path(option('--script') or ROOT / 'tts' / f'{chapter["id"]}.tagged.json')
        if not path.is_file():
            raise SystemExit(f'{path} not found: tag the chapter first (tts-tags skill) or pass --untagged')
        if check(build_script(chapter, DEFAULT_LIMIT), str(path)):
            raise SystemExit('The tagged script no longer matches the chapter: export and tag it again')
        script = json.loads(path.read_text(encoding='utf-8'))

    voices = load_json(VOICES_FILE)
    used = {i['voice'] for c in script['chunks'] for i in c['inputs']}
    missing = sorted(v for v in used if not voices.get(v, {}).get('voiceId'))
    if missing:
        raise SystemExit(f'No voiceId in tts/voices.json for: {", ".join(missing)}')
    voice_ids = {name: voices[name]['voiceId'] for name in used}

    chunks = script['chunks']
    # A script tagged before tts/stress.txt changed still gets the current marks
    for chunk in chunks:
        for item in chunk['inputs']:
            item['text'] = apply_stress(item['text'])
    count = len(chunks)
    selected = parse_range(option('--chunks'), count) if option('--chunks') else list(range(1, count + 1))
    retake = set(parse_range(option('--retake'), count)) if option('--retake') else set()
    selected = sorted(set(selected) | retake)
    work.mkdir(parents=True, exist_ok=True)
    manifest_path = work / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}

    sent = 0
    texts = [' '.join(plain(i['text']) for i in c['inputs']) for c in chunks]
    for n in selected:
        chunk = chunks[n - 1]
        fingerprint = hashlib.sha256(json.dumps([chunk['inputs'], [voice_ids[i['voice']] for i in chunk['inputs']],
                                                 script['model_id'], OUTPUT_FORMAT], ensure_ascii=False).encode()).hexdigest()
        file = work / f'chunk-{n:02}.mp3'
        if file.is_file() and manifest.get(str(n), {}).get('hash') == fingerprint and n not in retake:
            continue
        audio, request_id = generate(chunk, voice_ids, script['model_id'],
                                     texts[n - 2] if n > 1 else '', texts[n] if n < count else '')
        file.write_bytes(audio)
        size = sum(len(i['text']) for i in chunk['inputs'])
        sent += size
        manifest[str(n)] = {'hash': fingerprint, 'request_id': request_id, 'characters': size}
        manifest_path.write_text(json.dumps(manifest, indent=1))
        print(f'chunk {n}/{count}: paragraphs {chunk["paragraphs"][0]}-{chunk["paragraphs"][1]}, '
              f'{size} characters, {duration(file):.1f} s')

    ready = [n for n in range(1, count + 1) if (work / f'chunk-{n:02}.mp3').is_file()]
    print(f'sent {sent} characters; {len(ready)} of {count} chunks ready in {work.relative_to(ROOT)}')
    if len(ready) < count:
        print('The chapter is joined once every chunk is ready.')
        return
    out, starts = join(work, chapter['id'], count)
    times = paragraph_timings(chapter, script, starts, work)
    total = duration(out)
    (work / 'timings.json').write_text(json.dumps({'chapter': chapter['id'], 'duration': round(total, 1),
                                                    'paragraphs': times}) + '\n')
    print(f'{out.relative_to(ROOT)}: {total / 60:.1f} min, {out.stat().st_size / 1048576:.1f} MB. '
          f'Listen, retake chunks if needed, then run with --publish.')


if __name__ == '__main__':
    main()
