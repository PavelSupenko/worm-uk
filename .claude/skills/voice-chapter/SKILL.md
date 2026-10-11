---
name: voice-chapter
description: Produce and publish the multi-voice ElevenLabs voiceover of a chapter - tag it, check the budget, generate it chunk by chunk, let the user listen and retake parts, then upload it to Cloudflare R2 and link it on the site. Use when the user asks to voice, record or re-record a chapter.
---

# Voice a chapter

The pipeline is described in CLAUDE.md ("Voiceover pipeline"). Voices come from `tts/voices.json`;
every voice used in the chapter needs a `voiceId` there (step 1 casts the missing ones with the user).

## 0. Before you start

- `python3 tools/check_chapters.py` must pass: the voiceover is generated from the chapter text.
- `tools/setup.sh` must pass on this machine: it installs ffmpeg and whisper.cpp with its model (local
  post-processing) and checks the credentials. `ELEVENLABS_API_KEY` and the `R2_*` variables live in
  `~/.zshrc`; if the session doesn't see them, ask the user to restart Claude Code. Never print them.

## 1. Voices: markup and casting

Settle the voices before tagging; a voice added later changes the chunks.

- **Markup.** Everything outside `data-voice` is read by the narrator. Older chapters (1.1–1.4, 1.6,
  1.x) were translated before voices existed: find the direct speech left unmarked (straight `"…"`
  quotes in 1.1–1.3, `“…”` elsewhere) and mark every speaker as CLAUDE.md describes, attributions
  outside the voice spans, straight quotes turned into `“…”`. A key nobody has yet goes into
  `tts/voices.json` with a `description` (who, age, manner). Run the validator and commit the markup.
- **Casting.** For every voice key without a `voiceId`, follow `docs/voiceover-pipeline.md`
  ("Кастинг голосов"): a shortlist of English or European voices from `/v1/shared-voices`
  (`rate` 1, long `notice_period`) with their previews, then, for the ones the user picks, a sample of
  a scene from this chapter voiced with the rest of the cast (files side by side in
  `tts/audio/<id>/compare/`). The user chooses by ear. Add the chosen voice to the account as
  `worm · <key> · <name>` (`/v1/voices/add/{public_owner_id}/{voice_id}`), fill `voiceName` and
  `voiceId`, and remove rejected candidates so the account stays under 30 voices. Samples cost
  characters: report what they cost.
- A character with one or two lines can share a fitting voice with another minor character if the
  user agrees; ask instead of deciding.

## 2. Tag

Follow the `tts-tags` skill to write `tts/<id>.tagged.json`. Its `--check` must report 0 problems.

## 3. Budget

Add up the characters of all `text` values in the tagged script and read the remaining quota:

```
curl -s https://api.elevenlabs.io/v1/user/subscription -H "xi-api-key: $ELEVENLABS_API_KEY"
```

(`character_count` of `character_limit`). Tell the user what the chapter will cost and go on unless
it doesn't fit; a chapter is usually 10,000–15,000 characters, each retake costs one chunk again.

## 4. Generate

```
python3 tools/voice_chapter.py <id>
```

It sends one Text to Dialogue request per chunk and skips chunks that are already generated and
unchanged. When all chunks exist it post-processes them locally (whisper.cpp alignment, narrator asides
sped up 1.15×, one gain per voice, chunk edges trimmed, the whole chapter sped up 1.05×, -18 LUFS) into
`tts/audio/<id>/<id>.mp3` with `timings.json` (exact paragraph starts). A chapter takes several minutes;
run it in the background.

- The output lists every voice's loudness and gain. "calibrated" means the gain was stored in
  `tts/voices.json` (commit it with the chapter); "provisional" means the voice spoke too little to
  calibrate. Report gains that hit ±8 dB: such a voice may be a poor match for the cast.
- A chunk with less than 85% of its words aligned is left unprocessed; mention it to the user.
- `--no-post` joins the raw chunks; `--recalibrate` measures the voices again.

## 5. Listen and fix

- Open the result for the user: `open tts/audio/<id>/<id>.mp3`. Single chunks are `chunk-NN.mp3`.
- When the user points at a moment, find the chunk from `timings.json` (paragraph start times) and the
  chunk ranges in the tagged script.
- Fix by changing tags in that chunk of `tts/<id>.tagged.json` (re-run the `--check`), then run the
  generator again: changed chunks are regenerated automatically. `--retake N` regenerates chunk N as it is,
  for a take that was just unlucky.
- A wrong stress: add the word to `tts/stress.txt` (stressed vowel in capitals; a phrase if the stress
  depends on the meaning) or put a U+0301 mark after the vowel in that chunk of the tagged script, then
  run the generator again: the changed chunks are regenerated.
- A wrong word means the chapter text needs an edit: fix the chapter, run the validator, export and
  re-tag the affected chunk.

## 6. Publish (only after the user approves the recording)

```
python3 tools/voice_chapter.py <id> --publish
python3 tools/check_chapters.py
```

This uploads the MP3 to R2 under a content-hashed name, writes `assets/timings/<id>.json` and points
`audioFile` in `assets/chapters.json` at the R2 URL. Commit the tagged script, `chapters.json`, the
timings and `tts/voices.json` if gains were calibrated ("Add voiceover for <id>"), push, and check
after the deploy that the live `chapters.json` points at the new file and R2 serves it with the site's
CORS header.

Anything learned while voicing (a tag that works, a pronunciation trick, a new rule) goes into
`docs/voiceover-pipeline.md` and, if it is a rule for the agent, into the `tts-tags` skill.
