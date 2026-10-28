---
name: publish-chapter
description: Publish a finished chapter of Worm - upload the approved voiceover to Cloudflare R2, take the draft mark off the chapter, validate, commit, push and check the live site. Use when the user approves a recording, or asks to publish or release a chapter.
---

# Publish a chapter

The last step after `voice-chapter`. Run it only when the user has listened to the recording and approved it:
the request to publish is that approval. Credentials are in the environment (see CLAUDE.md, "Voiceover
pipeline"); never print them.

## 1. Upload the voiceover

```
python3 tools/voice_chapter.py <id> --publish
```

It uploads `tts/audio/<id>/<id>.mp3` to R2 under a content-hashed name, writes `assets/timings/<id>.json` and
points `audioFile` in `assets/chapters.json` at the R2 URL. Nothing is regenerated as long as the tagged script
and `tts/stress.txt` are unchanged since the recording; that's why the next step comes after it.

## 2. Notes from listening

A wrong stress or a tag the user heard but decided to keep goes in now, after the upload, so the published
recording stays the approved one: the word in all its forms under a "Heard wrong in <id>" section at the end of
`tts/stress.txt`, a tag lesson in `docs/voiceover-pipeline.md` or the `tts-tags` skill. Later chapters benefit;
a new run of `voice_chapter.py <id>` would regenerate the chunks these changes touch.

## 3. Take off the draft mark

In `assets/chapters.json` remove `"status": "draft"` from the chapter's entry (the user's text has been
proofread and approved). Leave other chapters alone.

## 4. Validate, commit, push

```
python3 tools/check_chapters.py     # 0 errors, 0 warnings
```

Commit only your own paths, as "Publish <id>": `assets/chapters.json`, `assets/timings/<id>.json`, and when
changed `tts/voices.json` (gains calibrated on this chapter) and `tts/stress.txt`. Then push to `master`.

## 5. Check the live site

Wait for the deploy, then check what readers get:

```
gh run watch $(gh run list --workflow pages.yml --limit 1 --json databaseId -q '.[0].databaseId') --exit-status
curl -s "https://pavelsupenko.github.io/worm-uk/assets/chapters.json?t=$(date +%s)"   # the chapter has the new audioFile and no status
curl -sI -H "Origin: https://pavelsupenko.github.io" <audioFile URL>                  # 200, audio/mpeg, Access-Control-Allow-Origin
curl -s -o /dev/null -w '%{http_code}\n' https://pavelsupenko.github.io/worm-uk/<id>.html   # 200
```

## 6. Report

The chapter's URL, the R2 file, what was checked, and the notes added in step 2.
