---
name: voice-chapter
description: Produce and publish the multi-voice ElevenLabs voiceover of a chapter - tag it, check the budget, generate it chunk by chunk, let the user listen and retake parts, then upload it to Cloudflare R2 and link it on the site. Use when the user asks to voice, record or re-record a chapter.
---

# Voice a chapter

The pipeline is described in CLAUDE.md ("Voiceover pipeline"). Voices come from `tts/voices.json`;
every voice used in the chapter needs a `voiceId` there (ask the user to pick one if it's missing).

## 0. Before you start

- `python3 tools/check_chapters.py` must pass: the voiceover is generated from the chapter text.
- `ELEVENLABS_API_KEY` must be in the environment (and the `R2_*` variables for publishing). If a
  variable is missing, ask the user to restart Claude Code: they live in `~/.zshrc`. Never print them.

## 1. Tag

Follow the `tts-tags` skill to write `tts/<id>.tagged.json`. Its `--check` must report 0 problems.

## 2. Budget

Add up the characters of all `text` values in the tagged script and read the remaining quota:

```
curl -s https://api.elevenlabs.io/v1/user/subscription -H "xi-api-key: $ELEVENLABS_API_KEY"
```

(`character_count` of `character_limit`). Tell the user what the chapter will cost and go on unless
it doesn't fit; a chapter is usually 10,000–15,000 characters, each retake costs one chunk again.

## 3. Generate

```
python3 tools/voice_chapter.py <id>
```

It sends one Text to Dialogue request per chunk, skips chunks that are already generated and
unchanged, and when all chunks exist joins them into `tts/audio/<id>/<id>.mp3` with
`timings.json` (paragraph start times). A chapter takes several minutes; run it in the background.

## 4. Listen and fix

- Open the result for the user: `open tts/audio/<id>/<id>.mp3`. Single chunks are `chunk-NN.mp3`.
- When the user points at a moment, find the chunk from `timings.json` (paragraph start times) and the
  chunk ranges in the tagged script.
- Fix by changing tags in that chunk of `tts/<id>.tagged.json` (re-run the `--check`), then run the
  generator again: changed chunks are regenerated automatically. `--retake N` regenerates chunk N as it is,
  for a take that was just unlucky.
- A wrong word or stress usually means the chapter text needs an edit: fix the chapter, run the
  validator, export and re-tag the affected chunk.

## 5. Publish (only after the user approves the recording)

```
python3 tools/voice_chapter.py <id> --publish
python3 tools/check_chapters.py
```

This uploads the MP3 to R2 under a content-hashed name, writes `assets/timings/<id>.json` and points
`audioFile` in `assets/chapters.json` at the R2 URL. Commit the tagged script, `chapters.json` and the
timings ("Add voiceover for <id>"), push, and check after the deploy that the chapter page plays the
new audio. If the chapter had an old MP3 in `audio/`, ask the user before removing it from the repository.
