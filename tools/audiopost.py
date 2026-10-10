#!/usr/bin/env python3
"""Post-processing of voiced audio, aligned with its text by local speech
recognition (whisper.cpp; tools/setup.sh installs it and the model).

Used by tools/voice_chapter.py for whole chapters. As a command it processes
one chunk, for experiments:

    python3 tools/audiopost.py CHUNK.mp3 --chapter 1.5 --chunk 7 [--tempo 1.15]
        [--no-tempo] [--no-balance] [--inputs 4-11] [--out OUT.mp3]

--inputs limits the text to some inputs of the chunk, for audio that voices only them.

1. whisper.cpp transcribes the audio with a time for every word; the words are
   matched to the known text (tolerant to recognition mistakes), which gives
   the start and end of every input (turn) and of every word.
2. Cuts go in the middle of the pauses between turns, so nothing clicks.
3. Narrator asides, the narration between two parts of one character's line in
   the same paragraph, are sped up with atempo (pitch is kept); Eleven v4
   ignores speed tags.
4. Every voice gets one constant gain towards VOICE_LUFS, so the voices sound
   equally loud while a shout stays louder than a whisper. The result is then
   brought to TARGET_LUFS with one linear gain under the true-peak limit.
"""
import difflib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from chapterlib import chapter_root, find_chapter, read_chapter, voice_runs
from export_tts import ACUTE, DEFAULT_LIMIT, TAG, build_script

MODEL = Path(os.environ.get('WHISPER_MODEL_DIR', Path.home() / '.cache' / 'whisper')) / 'ggml-large-v3-turbo-q5_0.bin'
TEMPO = 1.15             # speed of the narrator's asides (chosen by ear on 1.5)
MIN_ASIDE_WORDS = 4
VOICE_LUFS = -20.0       # every voice is moved towards this loudness
MAX_GAIN_DB = 8.0        # never move a voice by more than this
TARGET_LUFS = -18.0      # usual loudness for spoken-word audio
MAX_TRUE_PEAK = -1.0
MIN_COVERAGE = 0.85      # below this share of aligned words a chunk is left as it is
BITRATE = '64k'
WORD = re.compile(r"[\w'’ʼ]+")


def words_of(text):
    """Normalized words: lowercase, no stress marks or tags, one apostrophe."""
    text = TAG.sub(' ', text).replace(ACUTE, '').lower()
    return [w.replace('’', "'").replace('ʼ', "'") for w in WORD.findall(text)]


def duration(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout)


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


def analyse(audio, inputs):
    """Aligns the audio with the inputs' text. Returns a dict (JSON-friendly,
    so callers can cache it): words, input index and [start, end] of every
    expected word, spans of every input, aligned share, duration."""
    expected = [(word, n) for n, item in enumerate(inputs) for word in words_of(item['text'])]
    recognized = transcribe(audio)
    times = [None] * len(expected)
    matcher = difflib.SequenceMatcher(None, [w for w, _ in expected], [w for w, _, _ in recognized], autojunk=False)
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            _, start, end = recognized[block.b + k]
            times[block.a + k] = [start, end]
    coverage = sum(t is not None for t in times) / max(1, len(expected))
    # Words the recognizer got wrong take their time from the matched neighbours
    known = [i for i, t in enumerate(times) if t]
    for i, t in enumerate(times):
        if t is None:
            before = max((k for k in known if k < i), default=None)
            after = min((k for k in known if k > i), default=None)
            start = times[before][1] if before is not None else (times[after][0] if after is not None else 0.0)
            end = times[after][0] if after is not None else start
            times[i] = [start, max(start, end)]
    spans = []
    for n in range(len(inputs)):
        own = [times[i] for i, (_, m) in enumerate(expected) if m == n]
        spans.append([min(s for s, _ in own), max(e for _, e in own)] if own else None)
    return {'words': [w for w, _ in expected], 'inputs': [m for _, m in expected], 'times': times,
            'spans': spans, 'coverage': coverage, 'duration': duration(audio)}


def segments_of(analysis, inputs):
    """[(start, end, voice)] for every input, cut in the middle of the pauses."""
    spans = [list(span) if span else None for span in analysis['spans']]
    for i, span in enumerate(spans):
        if span is None:  # an input without words (only tags): borrow the neighbour's edge
            edge = spans[i - 1][1] if i else 0.0
            spans[i] = [edge, edge]
    cuts = [0.0]
    for (_, end), (start, _) in zip(spans, spans[1:]):
        cuts.append((end + start) / 2 if start > end else start)
    cuts.append(analysis['duration'])
    return [(cuts[i], max(cuts[i], cuts[i + 1]), item['voice']) for i, item in enumerate(inputs)]


def aside_keys(chapter):
    """Narration between two runs of one character within one paragraph,
    as normalized word strings (compare with aside_key)."""
    root = chapter_root(read_chapter(chapter))
    narrator = root.attrs['data-narrator']
    asides = set()
    for runs in voice_runs(root):
        for i in range(1, len(runs) - 1):
            voice, text = runs[i]
            if voice == narrator and runs[i - 1][0] == runs[i + 1][0] != narrator and len(words_of(text)) >= MIN_ASIDE_WORDS:
                asides.add(aside_key(text))
    return asides


def aside_key(text):
    return ' '.join(words_of(text))


def measure(audio, parts=None):
    """(integrated LUFS, true peak dBTP) of the file or of [(start, end)] parts
    joined; (None, None) when there is too little sound to measure."""
    if parts:
        graph = ';'.join(f'[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS[p{i}]' for i, (s, e) in enumerate(parts))
        graph += ';' + ''.join(f'[p{i}]' for i in range(len(parts))) + f'concat=n={len(parts)}:v=0:a=1,ebur128=peak=true'
    else:
        graph = '[0:a]ebur128=peak=true'
    out = subprocess.run(['ffmpeg', '-nostats', '-i', str(audio), '-filter_complex', graph, '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    summary = out[out.rfind('Summary:'):]
    lufs = re.search(r'I:\s+(-?[\d.]+) LUFS', summary)
    peak = re.search(r'Peak:\s+(-?[\d.]+|-inf) dBFS', summary)
    if not lufs or float(lufs.group(1)) <= -70:
        return None, None
    return float(lufs.group(1)), float(peak.group(1).replace('-inf', '-99')) if peak else None


def voice_loudness(audio, segments):
    """{voice: (LUFS, seconds)} measured over all of a voice's segments."""
    result = {}
    for voice in sorted({v for _, _, v in segments}):
        parts = [(s, e) for s, e, v in segments if v == voice and e - s > 0.05]
        seconds = sum(e - s for s, e in parts)
        if seconds >= 0.5:
            lufs, _ = measure(audio, parts)
            if lufs is not None:
                result[voice] = (lufs, seconds)
    return result


def combine_loudness(measurements):
    """Energy-weighted loudness of several (LUFS, seconds) measurements."""
    seconds = sum(s for _, s in measurements)
    energy = sum(10 ** (lufs / 10) * s for lufs, s in measurements)
    return 10 * math.log10(energy / seconds), seconds


def gain_for(lufs):
    return max(-MAX_GAIN_DB, min(MAX_GAIN_DB, VOICE_LUFS - lufs))


def render(audio, segments, gains, fast, tempo, out):
    """Writes a WAV with every segment's voice gain and the asides sped up."""
    graph = []
    for i, (start, end, voice) in enumerate(segments):
        chain = f'[0:a]atrim={start:.3f}:{end:.3f},asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=mono'
        if gains.get(voice):
            chain += f',volume={gains[voice]:.2f}dB'
        if i in fast and tempo != 1.0:
            chain += f',atempo={tempo}'
        graph.append(chain + f'[s{i}]')
    graph.append(''.join(f'[s{i}]' for i in range(len(segments))) + f'concat=n={len(segments)}:v=0:a=1[mix]')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(audio), '-filter_complex', ';'.join(graph),
                    '-map', '[mix]', '-c:a', 'pcm_s16le', str(out)], check=True)


def time_map(segments, fast, tempo):
    """Maps a time in the original audio to the processed (sped-up) audio."""
    starts, position = [], 0.0
    for i, (start, end, _) in enumerate(segments):
        starts.append(position)
        position += (end - start) / (tempo if i in fast else 1.0)

    def mapped(t):
        for i, (start, end, _) in enumerate(segments):
            if t < end or i == len(segments) - 1:
                factor = 1 / tempo if i in fast else 1.0
                return starts[i] + max(0.0, t - start) * factor
        return position
    return mapped


def finalize(wav, out):
    """One linear gain to TARGET_LUFS under the true-peak limit, MP3 encode."""
    lufs, peak = measure(wav)
    gain = 0.0 if lufs is None else min(TARGET_LUFS - lufs, MAX_TRUE_PEAK - (peak if peak is not None else -99))
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(wav), '-af', f'volume={gain:.2f}dB',
                    '-ac', '1', '-ar', '44100', '-c:a', 'libmp3lame', '-b:a', BITRATE, str(out)], check=True)
    return gain


def main():
    args = sys.argv[1:]
    option = lambda name, default=None: args[args.index(name) + 1] if name in args else default
    audio = Path(args[0])
    chapter = find_chapter(option('--chapter'))
    tempo = 1.0 if '--no-tempo' in args else float(option('--tempo', TEMPO))
    out = Path(option('--out', audio.with_name(audio.stem + ' (processed).mp3')))
    inputs = build_script(chapter, DEFAULT_LIMIT)['chunks'][int(option('--chunk')) - 1]['inputs']
    if option('--inputs'):
        first, last = map(int, option('--inputs').split('-'))
        inputs = inputs[first - 1:last]

    analysis = analyse(audio, inputs)
    print(f'aligned {analysis["coverage"]:.0%} of the words')
    segments = segments_of(analysis, inputs)
    asides = aside_keys(chapter)
    fast = {i for i, item in enumerate(inputs) if aside_key(item['text']) in asides}
    gains = {}
    if '--no-balance' not in args:
        for voice, (lufs, seconds) in voice_loudness(audio, segments).items():
            gains[voice] = gain_for(lufs)
            print(f'{voice:8} {lufs:6.1f} LUFS over {seconds:4.1f} s -> gain {gains[voice]:+.1f} dB')
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / 'mix.wav'
        render(audio, segments, gains, fast, tempo, wav)
        finalize(wav, out)
    for i in sorted(fast):
        start, end, voice = segments[i]
        print(f'aside {i + 1} ({voice}): {end - start:.1f} s -> {(end - start) / tempo:.1f} s')
    print(f'{out.name}: {analysis["duration"]:.1f} s -> {duration(out):.1f} s, {measure(out)[0]:.1f} LUFS')


if __name__ == '__main__':
    main()
