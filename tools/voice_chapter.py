#!/usr/bin/env python3
"""Voices a chapter with ElevenLabs Text to Dialogue (Eleven v4), post-processes
it locally and publishes it.

Usage:
    python3 tools/voice_chapter.py 1.5                  # generate missing chunks, then post-process and join
    python3 tools/voice_chapter.py 1.5 --chunks 3-4     # only some chunks (tests, partial work)
    python3 tools/voice_chapter.py 1.5 --retake 3       # generate chunk 3 again
    python3 tools/voice_chapter.py 1.5 --publish        # upload to R2, point chapters.json at it
Options:
    --script PATH     use another tagged script instead of tts/<id>.tagged.json
    --untagged        use the plain export, without audio tags
    --no-post         join the raw chunks without post-processing
    --recalibrate     measure the voices again instead of using gainDb from tts/voices.json

Generation: every chunk of the script (whole paragraphs, see tools/export_tts.py)
is one Text to Dialogue request with the narrator and the characters, so the
model hears the scene; the neighbouring chunks' text goes along as
previous_text/future_text. The tagged script is checked against the chapter
first, stress marks from tts/stress.txt are applied, and chunks whose content
didn't change are not sent again.

Post-processing (tools/audiopost.py, local whisper.cpp): every chunk is aligned
with its text; narrator asides inside a character's line are sped up, and every
voice gets its constant gain. The gain is measured once over a chapter where the
voice speaks for at least CALIBRATION_SECONDS and stored as gainDb in
tts/voices.json together with the voiceId it was measured for (gainVoiceId), so
voices keep the same level across chapters and a recast voice is measured again. The silence at
the edges of every chunk is trimmed, so joins sound like pauses inside a chunk; the chapter is
sped up by audiopost.CHAPTER_TEMPO, brought to -18 LUFS and encoded once at 64 kbps; timings.json holds the exact
start of every paragraph (its first word) in the final audio.

Work files are in tts/audio/<id>/ (not committed): chunk-NN.mp3, manifest.json,
align-NN.json, post-NN.wav, <id>.mp3 (the chapter) and timings.json.
--publish uploads <id>.mp3 to R2 under a content-hashed name, writes
assets/timings/<id>.json and sets audioFile in assets/chapters.json.
Needs ELEVENLABS_API_KEY (and R2_* for --publish), ffmpeg and, for
post-processing, whisper.cpp with its model (tools/setup.sh).
"""
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import audiopost
from chapterlib import CHAPTERS_FILE, ROOT, VOICES_FILE, chapter_root, find_chapter, load_json, read_chapter, voice_runs
from export_tts import DEFAULT_LIMIT, TAG, apply_stress, build_script, check

API = 'https://api.elevenlabs.io/v1/text-to-dialogue'
# Chunks come at a higher bitrate; the chapter is encoded once at the end
OUTPUT_FORMAT = 'mp3_44100_128'
LANGUAGE = 'uk'
CONTEXT_CHARS = 100        # API limit for previous_text / future_text
CHUNK_PAUSE = 0.25         # silence between chunks on top of their trimmed edges (they end on a paragraph)
CALIBRATION_SECONDS = 20   # speech a voice needs in a chapter before its gain is stored

duration = audiopost.duration


def plain(text):
    return ' '.join(TAG.sub(' ', text).split())


def parse_range(value, count):
    numbers = set()
    for part in value.split(','):
        first, _, last = part.partition('-')
        numbers.update(range(int(first), int(last or first) + 1))
    return sorted(n for n in numbers if 1 <= n <= count)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


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


def join(files, out, encode=True):
    """Decodes the parts, puts a short pause between them and writes one file
    (MP3 at audiopost.BITRATE, or WAV). Returns the start time of every part."""
    inputs, graph = [], []
    for i, file in enumerate(files):
        inputs += ['-i', str(file)]
        pad = f',apad=pad_dur={CHUNK_PAUSE}' if i < len(files) - 1 else ''
        graph.append(f'[{i}:a]aformat=sample_rates=44100:channel_layouts=mono{pad}[a{i}]')
    graph.append(''.join(f'[a{i}]' for i in range(len(files))) + f'concat=n={len(files)}:v=0:a=1[out]')
    codec = ['-c:a', 'libmp3lame', '-b:a', audiopost.BITRATE] if encode else ['-c:a', 'pcm_s16le']
    subprocess.run(['ffmpeg', '-y', '-v', 'error', *inputs, '-filter_complex', ';'.join(graph), '-map', '[out]',
                    *codec, str(out)], check=True)
    starts, position = [], 0.0
    for file in files:
        starts.append(position)
        position += duration(file) + CHUNK_PAUSE
    return starts


def paragraph_lengths(chapter):
    runs = voice_runs(chapter_root(read_chapter(chapter)))
    return ([sum(len(text) for _, text in r) for r in runs],
            [len(audiopost.words_of(' '.join(text for _, text in r))) for r in runs])


def estimate_starts(times, lengths, chunk, start, length):
    """Fills the paragraphs of a chunk by their share of its characters."""
    first, last = chunk['paragraphs']
    total = sum(lengths[p - 1] for p in range(first, last + 1)) or 1
    before = 0
    for p in range(first, last + 1):
        if times[p - 1] is None:
            times[p - 1] = round(start + length * before / total, 1)
        before += lengths[p - 1]


def save_voices(voices):
    lines = []
    for name, entry in voices.items():
        ordered = {k: entry[k] for k in ('description', 'voiceName', 'voiceId', 'gainDb', 'gainVoiceId') if k in entry}
        lines.append(f'    {json.dumps(name)}: {json.dumps(ordered, ensure_ascii=False)}')
    VOICES_FILE.write_text('{\n' + ',\n'.join(lines) + '\n}\n', encoding='utf-8')


def analysis_of(work, n, chunk):
    """Alignment of chunk n, cached in align-NN.json by audio and text."""
    audio = work / f'chunk-{n:02}.mp3'
    key = sha256(audio.read_bytes() + json.dumps([i['text'] for i in chunk['inputs']], ensure_ascii=False).encode())
    cache = work / f'align-{n:02}.json'
    if cache.is_file():
        cached = json.loads(cache.read_text())
        if cached.get('key') == key:
            return cached['analysis']
    analysis = audiopost.analyse(audio, chunk['inputs'])
    cache.write_text(json.dumps({'key': key, 'analysis': analysis}))
    return analysis


def post_process(chapter, script, work, voices, recalibrate=False, save=True):
    """Aligns, balances and speeds up every chunk, joins the chapter.
    Returns (chapter mp3, paragraph start times)."""
    chunks = script['chunks']
    asides = audiopost.aside_keys(chapter)
    plans = []
    for n, chunk in enumerate(chunks, start=1):
        analysis = analysis_of(work, n, chunk)
        usable = analysis['coverage'] >= audiopost.MIN_COVERAGE
        if not usable:
            print(f'chunk {n}: only {analysis["coverage"]:.0%} of the words aligned, left unprocessed')
        segments = audiopost.segments_of(analysis, chunk['inputs'])
        if usable:
            segments = audiopost.trim_edges(segments, work / f'chunk-{n:02}.mp3', chunk['inputs'])
        fast = {i for i, item in enumerate(chunk['inputs']) if audiopost.aside_key(item['text']) in asides} if usable else set()
        plans.append((analysis, segments, fast, usable))

    # Voice loudness over the whole chapter
    measured = {}
    for n, (analysis, segments, fast, usable) in enumerate(plans, start=1):
        if usable:
            for voice, value in audiopost.voice_loudness(work / f'chunk-{n:02}.mp3', segments).items():
                measured.setdefault(voice, []).append(value)
    gains, changed = {}, False
    for voice in sorted({i['voice'] for c in chunks for i in c['inputs']}):
        entry = voices.get(voice, {})
        # A gain only holds for the voice it was measured on
        stored = entry.get('gainDb') if entry.get('gainVoiceId') == entry.get('voiceId') else None
        if voice in measured:
            lufs, seconds = audiopost.combine_loudness(measured[voice])
            computed = audiopost.gain_for(lufs)
        else:
            lufs = seconds = computed = None
        if stored is not None and not recalibrate:
            gains[voice], note = stored, 'stored'
        elif computed is not None:
            gains[voice] = round(computed, 1)
            if seconds >= CALIBRATION_SECONDS:
                voices[voice]['gainDb'] = gains[voice]
                voices[voice]['gainVoiceId'] = voices[voice]['voiceId']
                changed, note = True, 'calibrated'
            else:
                note = f'provisional, only {seconds:.0f} s of speech'
        else:
            gains[voice], note = 0.0, 'not measured'
        level = f'{lufs:6.1f} LUFS over {seconds:5.1f} s' if lufs is not None else 'too little speech'
        print(f'{voice:8} {level} -> gain {gains[voice]:+.1f} dB ({note})')
    if changed and save:
        save_voices(voices)
        print('tts/voices.json: gainDb updated, commit it with the chapter')

    rendered = []
    for n, (analysis, segments, fast, usable) in enumerate(plans, start=1):
        out = work / f'post-{n:02}.wav'
        audiopost.render(work / f'chunk-{n:02}.mp3', segments, gains if usable else {}, fast, audiopost.TEMPO, out)
        rendered.append(out)
    joined = work / 'joined.wav'
    starts = join(rendered, joined, encode=False)
    final = work / f'{chapter["id"]}.mp3'
    audiopost.finalize(joined, final)
    joined.unlink()

    # Exact paragraph starts: the first word of the paragraph in the final audio
    lengths, word_counts = paragraph_lengths(chapter)
    times = [None] * len(lengths)
    for (analysis, segments, fast, usable), chunk, start, file in zip(plans, chunks, starts, rendered):
        first, last = chunk['paragraphs']
        counts = word_counts[first - 1:last]
        if usable and sum(counts) == len(analysis['words']):
            mapped = audiopost.time_map(segments, fast, audiopost.TEMPO)
            index = 0
            for p, count in zip(range(first, last + 1), counts):
                if times[p - 1] is None and count:
                    times[p - 1] = round((start + mapped(analysis['times'][index][0])) / audiopost.CHAPTER_TEMPO, 1)
                index += count
        else:  # a paragraph split across chunks, or a poor alignment
            estimate_starts(times, lengths, chunk, start / audiopost.CHAPTER_TEMPO,
                            duration(file) / audiopost.CHAPTER_TEMPO)
    sped = sum(len(fast) for _, _, fast, _ in plans)
    print(f'{sped} narrator asides sped up by {audiopost.TEMPO}, the chapter by {audiopost.CHAPTER_TEMPO}')
    return final, times


def publish(chapter, work):
    sys.path.insert(0, str(Path(__file__).parent))
    import r2

    audio = work / f'{chapter["id"]}.mp3'
    timings = work / 'timings.json'
    if not audio.is_file() or not timings.is_file():
        raise SystemExit(f'Nothing to publish: generate the whole chapter first ({audio} is missing)')
    data = audio.read_bytes()
    folder = Path(chapter['textFile']).parent.name  # e.g. 1.gestation
    key = f'{folder}/{chapter["id"]}-{sha256(data)[:8]}.mp3'
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
        fingerprint = sha256(json.dumps([chunk['inputs'], [voice_ids[i['voice']] for i in chunk['inputs']],
                                         script['model_id'], OUTPUT_FORMAT], ensure_ascii=False).encode())
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

    if '--no-post' in args:
        out = work / f'{chapter["id"]}.mp3'
        files = [work / f'chunk-{n:02}.mp3' for n in range(1, count + 1)]
        starts = join(files, out)
        lengths, _ = paragraph_lengths(chapter)
        times = [None] * len(lengths)
        for chunk, start, file in zip(chunks, starts, files):
            estimate_starts(times, lengths, chunk, start, duration(file))
    else:
        out, times = post_process(chapter, script, work, voices, recalibrate='--recalibrate' in args)
    total = duration(out)
    (work / 'timings.json').write_text(json.dumps({'chapter': chapter['id'], 'duration': round(total, 1),
                                                    'paragraphs': times}) + '\n')
    print(f'{out.relative_to(ROOT)}: {total / 60:.1f} min, {out.stat().st_size / 1048576:.1f} MB, '
          f'{audiopost.measure(out)[0]:.1f} LUFS. Listen, retake chunks if needed, then run with --publish.')


if __name__ == '__main__':
    main()
