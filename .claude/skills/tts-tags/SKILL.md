---
name: tts-tags
description: Prepare a chapter for ElevenLabs Eleven v4 voiceover by adding audio tags ([whispers], [sarcastic], [pause]...) to its exported dialogue script without changing any words. Use when the user wants a chapter ready for voiceover or asks to tag a chapter for TTS.
---

# Tag a chapter for the voiceover

The voiceover is generated with ElevenLabs Eleven v4 through the Text to Dialogue API. Tags are
natural-language directions in square brackets inside the text; they affect the speech that follows
them within the same input.

## 1. Export

```
python3 tools/export_tts.py <chapter id>
```

This writes `tts/<id>.json`: `chunks` (one API request each, whole paragraphs, under 1800
characters), each with `inputs` of `{"voice", "text"}`. Voices are described in `tts/voices.json`.
The chapter itself is in the file listed for it in `assets/chapters.json`, if more context helps.

## 2. Write `tts/<id>.tagged.json`

Copy the export and only insert tags into the `text` values.

- **Never change the text**: no added, removed or reordered words, letters or punctuation; don't fix typos (report them instead). Don't merge or split inputs or chunks, don't touch `voice` or `paragraphs`.
- Tags are short English directions placed right before the words they affect: `[sarcastic]`, `[whispers]`, `[shouting]`, `[angry]`, `[nervous]`, `[out of breath]`, `[laughs]`, `[sighs]`, `[pause]`, `[long pause]`, or your own words such as `[dry, unimpressed]` or `[through gritted teeth]`.
- Dialogue gets most of the tags: read each line in context (who speaks, to whom, what just happened) and give the delivery the scene implies. A neutral line needs no tag.
- The narrator stays mostly untagged. Use tags for clear shifts: tension in a fight, a quiet or tired moment, a dry joke, and `[pause]` or `[long pause]` at scene breaks and strong dramatic beats.
- Density: on average about one tag per two to four sentences of dialogue and much less in narration; at most one delivery tag per sentence (reactions like `[laughs]` aside).
- Tags count towards the API limit: every chunk must stay at or under 2000 characters including tags.

## 3. Check

```
python3 tools/export_tts.py <id> --check tts/<id>.tagged.json
```

It must report 0 problems: same chunks and voices, the same text once tags are removed, no chunk over
2000 characters. Fix anything it reports and run it again.

## 4. Finish

- Commit `tts/<id>.tagged.json` ("Add voiceover tags for <id>"). The plain export `tts/<id>.json` is ignored by git.
- If the chapter text changes later, the check fails: export again and re-tag the changed chunks.
- Report the typos or odd phrasings you noticed in the text, and any line where the right delivery was unclear.
