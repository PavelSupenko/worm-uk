#!/usr/bin/env python3
"""Post-processing of a voiced chunk, aligned with its text by local speech
recognition (whisper.cpp, installed by tools/setup.sh).

    python3 tools/audiopost.py CHUNK.mp3 --chapter 1.5 --chunk 7 [--tempo 1.2]
        [--no-tempo] [--no-balance] [--out OUT.mp3]

1. whisper.cpp transcribes the audio with a time for every word; the words are
   matched to the chunk's known text (tolerant to recognition mistakes), which
   gives the start and end of every input (turn).
2. Cuts go in the middle of the pauses between turns, so nothing clicks.
3. Narrator asides, the narration between two parts of one character's line in
   the same paragraph, are sped up with atempo (pitch is kept).
4. Every voice gets one constant gain so the voices sound equally loud: a shout
   stays louder than a whisper, only the voices are balanced against each other.
   The result is then brought to TARGET_LUFS with a single linear gain.
"""
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from chapterlib import chapter_root, find_chapter, read_chapter, voice_runs
from export_tts import ACUTE, DEFAULT_LIMIT, TAG, build_script

MODEL = Path(os.environ.get('WHISPER_MODEL_DIR', Path.home() / '.cache' / 'whisper')) / 'ggml-large-v3-turbo-q5_0.bin'
TEMPO = 1.2            # speed of the narrator's asides
MIN_ASIDE_WORDS = 4
MAX_GAIN_DB = 8.0      # never move a voice by more than this
TARGET_LUFS = -18.0    # usual loudness for spoken-word audio
MAX_TRUE_PEAK = -1.0
BITRATE = '64k'
WORD = re.compile(r"[\w'’ʼ]+")


def words_of(text):
    """Normalized words: lowercase, no stress marks or tags, one apostrophe."""
    text = TAG.sub(' ', text).replace(ACUTE, '').lower()
    return [w.replace('’', "'").replace('ʼ', "'") for w in WORD.findall(text)]


def transcribe(audio):
    """[(word, start, end)] in seconds, from whisper.cpp word-level segments."""
    if not MODEL.is_file():
        raise SystemExit(f'{MODEL} is missing: run tools/setup.sh')
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / 'audio.wav'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(audio), '-ar', '16000', '-ac', '1',
                        '-c:a', 'pcm_s16le', str(wav)], check=True)
        subprocess.run(['whisper-cli', '-m', str(MODEL), '-l', 'uk', '-f', str(wav), '-ojf', '-ml', '1', '-sow',
                        '-dtw', 'large.v3.turbo', '-np', '-of', str(Path(tmp) / 'out')],
                       check=True, capture_output=True)
        segments = json.loads((Path(tmp) / 'out.json').read_text())['transcription']
    result = []
    for segment in segments:
        for word in words_of(segment['text']):
            result.append((word, segment['offsets']['from'] / 1000, segment['offsets']['to'] / 1000))
    return result


def align(inputs, recognized):
    """(start, end) of every input, from the recognized words matched to the text."""
    expected = [(word, n) for n, item in enumerate(inputs) for word in words_of(item['text'])]
    times = [None] * len(expected)
    matcher = difflib.SequenceMatcher(None, [w for w, _ in expected], [w for w, _, _ in recognized], autojunk=False)
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            _, start, end = recognized[block.b + k]
            times[block.a + k] = (start, end)
    matched = sum(t is not None for t in times)
    # Words the recognizer got wrong take their time from the matched neighbours
    known = [i for i, t in enumerate(times) if t]
    for i, t in enumerate(times):
        if t is None:
            before = max((k for k in known if k < i), default=None)
            after = min((k for k in known if k > i), default=None)
            start = times[before][1] if before is not None else (times[after][0] if after is not None else 0)
            end = times[after][0] if after is not None else start
            times[i] = (start, max(start, end))
    spans = []
    for n in range(len(inputs)):
        own = [times[i] for i, (_, m) in enumerate(expected) if m == n]
        spans.append((min(s for s, _ in own), max(e for _, e in own)) if own else None)
    return spans, matched / max(1, len(expected))


def aside_texts(chapter):
    """Narration between two runs of one character within one paragraph."""
    root = chapter_root(read_chapter(chapter))
    narrator = root.attrs['data-narrator']
    asides = set()
    for runs in voice_runs(root):
        for i in range(1, len(runs) - 1):
            voice, text = runs[i]
            if voice == narrator and runs[i - 1][0] == runs[i + 1][0] != narrator and len(words_of(text)) >= MIN_ASIDE_WORDS:
                asides.add(' '.join(words_of(text)))
    return asides


def duration(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout)


def measure(audio, parts=None):
    """(integrated LUFS, true peak dBTP) of the whole file or of [(start, end)] parts joined."""
    if parts:
        graph = ';'.join(f'[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS[p{i}]' for i, (s, e) in enumerate(parts))
        graph += ';' + ''.join(f'[p{i}]' for i in range(len(parts))) + f'concat=n={len(parts)}:v=0:a=1,ebur128=peak=true'
    else:
        graph = '[0:a]ebur128=peak=true'
    out = subprocess.run(['ffmpeg', '-nostats', '-i', str(audio), '-filter_complex', graph, '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    summary = out[out.rfind('Summary:'):]
    lufs = float(re.search(r'I:\s+(-?[\d.]+) LUFS', summary).group(1))
    peak = float(re.search(r'Peak:\s+(-?[\d.]+|-inf) dBFS', summary).group(1).replace('-inf', '-99'))
    return lufs, peak


def main():
    args = sys.argv[1:]
    option = lambda name, default=None: args[args.index(name) + 1] if name in args else default
    audio = Path(args[0])
    chapter = find_chapter(option('--chapter'))
    number = int(option('--chunk'))
    tempo = 1.0 if '--no-tempo' in args else float(option('--tempo', TEMPO))
    balance = '--no-balance' not in args
    out = Path(option('--out', audio.with_name(audio.stem + ' (processed).mp3')))

    inputs = build_script(chapter, DEFAULT_LIMIT)['chunks'][number - 1]['inputs']
    spans, coverage = align(inputs, transcribe(audio))
    total = duration(audio)
    print(f'aligned {coverage:.0%} of the words')

    # Cut points in the middle of the pauses between turns
    cuts = [0.0]
    for (_, end), (start, _) in zip(spans, spans[1:]):
        cuts.append((end + start) / 2 if start > end else start)
    cuts.append(total)
    segments = [(cuts[i], cuts[i + 1], item) for i, item in enumerate(inputs)]

    asides = aside_texts(chapter)
    fast = {i for i, (_, _, item) in enumerate(segments) if ' '.join(words_of(item['text'])) in asides}

    gains = {}
    if balance:
        loudness = {}
        for voice in sorted({item['voice'] for item in inputs}):
            parts = [(s, e) for s, e, item in segments if item['voice'] == voice]
            loudness[voice] = measure(audio, parts)[0]
        reference = sum(loudness.values()) / len(loudness)
        for voice, lufs in loudness.items():
            gains[voice] = max(-MAX_GAIN_DB, min(MAX_GAIN_DB, reference - lufs))
            print(f'{voice:8} {lufs:6.1f} LUFS -> gain {gains[voice]:+.1f} dB')

    graph = []
    for i, (start, end, item) in enumerate(segments):
        chain = f'[0:a]atrim={start:.3f}:{end:.3f},asetpts=PTS-STARTPTS'
        if gains:
            chain += f',volume={gains[item["voice"]]:.2f}dB'
        if i in fast and tempo != 1.0:
            chain += f',atempo={tempo}'
        graph.append(chain + f'[s{i}]')
    graph.append(''.join(f'[s{i}]' for i in range(len(segments))) + f'concat=n={len(segments)}:v=0:a=1[mix]')
    with tempfile.TemporaryDirectory() as tmp:
        mixed = Path(tmp) / 'mix.wav'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(audio), '-filter_complex', ';'.join(graph),
                        '-map', '[mix]', str(mixed)], check=True)
        lufs, peak = measure(mixed)
        # One linear gain to the target, kept under the true-peak limit
        gain = min(TARGET_LUFS - lufs, MAX_TRUE_PEAK - peak)
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(mixed), '-af', f'volume={gain:.2f}dB',
                        '-c:a', 'libmp3lame', '-b:a', BITRATE, str(out)], check=True)
    for i in sorted(fast):
        start, end, item = segments[i]
        print(f'aside {i + 1} ({item["voice"]}, {len(words_of(item["text"]))} words): '
              f'{end - start:.1f} s -> {(end - start) / tempo:.1f} s')
    print(f'{out.name}: {duration(audio):.1f} s -> {duration(out):.1f} s, {measure(out)[0]:.1f} LUFS')


if __name__ == '__main__':
    main()
