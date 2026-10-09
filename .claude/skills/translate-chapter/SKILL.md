---
name: translate-chapter
description: Translate a new chapter of Worm into Ukrainian directly in this site's chapter markup (narrator, voices, replaceable names), register it and validate it. Use when the user gives an original chapter and asks to translate or add it.
---

# Translate a chapter

The user gives the original English chapter: pasted text or a path to a local file. If they give
only a chapter number, ask for the text. Don't fetch the original from the web, and never commit the
English original to the repository: only the translation goes in.

## 1. Read before translating

- `CLAUDE.md`, sections "Chapter text markup" and "Name sets": the format below follows them.
- The previous one or two chapters in `texts/`: tone, how dialogue is punctuated (“…” quotes, “— сказав він” attributions), recurring terms.
- `assets/names.json`: localized names and terms already chosen. Use them exactly.
- `tts/voices.json`: voice keys already in use.

## 2. Where the chapter goes

- File: `texts/<arc number>.<english arc name in lowercase>/<chapter id>.html`, e.g. `texts/2.insinuation/2.1.html`. Interludes use the id `<arc>.x` (more interludes in one arc: ask the user for the id).
- A new arc also needs an arc entry in `assets/chapters.json` with a Ukrainian `title`. Propose the title and ask the user to confirm it.

## 3. Translate

- Literary Ukrainian in the register of the previous chapters. Keep the meaning, voice and humor of the original; don't summarize or soften.
- **One original paragraph is one `<p>`.** Don't merge or split paragraphs: the voiceover chunks and text sync rely on paragraph boundaries.
- Flag puns, invented terms and anything you weren't sure about in the final report instead of guessing silently.

## 4. Mark up while writing

```html
<div data-narrator="Taylor">
    <p>Narration with <span data-name="Lung" data-case="родовий">Луна</span> and <span data-character="Emma">Емма</span>.</p>
    <p><span data-voice="Brian">“Пряма мова,”</span> — сказав <span data-name="Grue">Морок</span>.</p>
    <p data-voice="Lisa">“Абзац, який повністю є реплікою.”</p>
</div>
```

- `data-narrator`: whose voice reads the narration. Taylor for her chapters; for interludes the POV character, or `Reader` for neutral third person.
- `data-voice`: only on direct speech of someone other than the narrator. Wrap just the quoted words, the attribution stays with the narrator. A paragraph that is entirely one character's line gets `data-voice` on the `<p>`. The narrator's own lines need no markup.
- `data-name`: every cape name, team, organization or term that has an entry in `names.json`. The text inside is exactly the localized form, in the case the sentence needs (`data-case`; `data-form="множина"` for plural; both default to singular nominative). Choose the case from the sentence even when forms coincide.
- `data-character`: civilian names (Taylor, Emma, Danny…), styling only.
- Nothing else: no `<br>`, no inline styles, no other attributes.

## 5. New names and voices

- A new cape, team or term: add an entry to `assets/names.json` with `category`, a complete `localized` table (7 cases × 2 numbers), `translit` (a string if it doesn't decline) and `original` (only if it differs from the key). Keep the file's one-line-per-table format.
- Propose the localized translation yourself, but list every new name in the final report so the user can approve or change it before the chapter is published.
- A new speaking character: add it to `tts/voices.json` with a short description (age, gender, manner of speech) and `"voiceId": null`. Use one consistent English key per person.

## 6. Check

```
python3 tools/markup_names.py <id> --write      # marks names you missed; prints the ones it couldn't decide
python3 tools/check_chapters.py --fix           # must end with 0 errors and 0 warnings
```

Mark the "need a case" leftovers by hand, review the "guessed" ones, then run the validator again.

## 7. Register and commit

- Add `{"id": "<id>", "textFile": "...", "status": "draft"}` to the arc in `assets/chapters.json`. No `audioFile` until the voiceover exists.
- Optionally preview with `python3 -m http.server 8000` and `http://localhost:8000/chapter_template.html?ch=<id>`.
- Commit as "Add raw <id> text" together with the names.json, voices.json and chapters.json changes. A push to `master` publishes the chapter, so push only when the user asks.

## 8. Report to the user

- New names and their proposed translations, new voices, a new arc title if any.
- Places where the translation needs their decision.
