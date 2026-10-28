---
name: get-chapter
description: Get a new chapter of Worm onto the site - fetch the original from the web as numbered lines for the user to translate, propose the new names for approval, then mark the user's Ukrainian translation up (narrator, voices, replaceable names), register and validate it. Use when the user names the next chapter to work on, gives a translated chapter or asks to add, mark up or prepare a new chapter.
---

# Get a chapter onto the site

The user translates the chapter themselves. The skill works in two stages:

1. **Only a chapter number, no translation yet**: fetch the original (step 1), propose the new names and,
   for a new arc, the arc title (steps 3–4), and tell the user that `orig/<id>.txt` is ready to translate.
   Stop there.
2. **The translation is there**: pasted, a file in the repository, or a plain draft `orig/<id>.uk.txt` in the
   format of `docs/translation-brief.md` (numbered lines, names left in English). Run
   `python3 tools/fetch_original.py <id> --check-draft` on such a draft first: it must end with `0 problems`,
   otherwise the numbering, a paragraph or an italic run is off. If the user wants an editor's pass, run the
   `proofread-chapter` skill on the draft before the markup. Then steps 2–8.

Don't translate the chapter yourself and don't paste the original into the chat: *Worm* is Wildbow's text,
and a full translation reproduces it. Your part is everything around the text: the original as a reference,
the names, the markup and the checks.

## 1. Get the original

```
python3 tools/fetch_original.py <id>           # -> orig/<id>.txt, one numbered line per paragraph
python3 tools/fetch_original.py --list [ARC]   # ids, labels and addresses of the table of contents
python3 tools/fetch_original.py <id> --url URL # when the id matches several chapters (a second interlude in an arc)
```

`orig/` is ignored by git: never commit the original or copy it into a file the repository tracks. Use it to
find the names, terms and speakers, and to check paragraph boundaries. The tool also prints the folder name
of the arc (`texts/1.gestation/`).

## 2. Read before marking up

- `CLAUDE.md`, sections "Chapter text markup" and "Name sets": the format below follows them.
- The previous one or two chapters in `texts/`: how dialogue is punctuated (“…” quotes, “— сказав він” attributions), recurring terms.
- `assets/names.json`: localized names and terms already chosen. Use them exactly.
- `tts/voices.json`: voice keys already in use.

## 3. Where the chapter goes

- File: `texts/<arc number>.<english arc name in lowercase>/<chapter id>.html`, e.g. `texts/2.insinuation/2.1.html`. Interludes use the id `<arc>.x` (more interludes in one arc: ask the user for the id).
- A new arc also needs an arc entry in `assets/chapters.json` with a Ukrainian `title`. Propose the title and ask the user to confirm it. Translate the English word closely (Gestation → Визрівання, Insinuation → Натяк) instead of describing the arc's plot: the story later reveals that the arc titles are stages of a life cycle.

## 4. Names: propose, wait for approval

Before marking up, read the original and list every name the chapter introduces that `names.json` and the
glossary don't have yet: capes, teams and organizations, terms, and new civilian characters. Show one table:

| English | Proposed Ukrainian (nominative) | category | translit | stress | note |

Take the meaning into account for capes and terms (localized sets translate the meaning, `translit` keeps the
sound) and say which names the user's text already uses. Ask the user when a stress is unclear, foreign names
especially. **Wait for the user's answer** unless they have said to go ahead; a name changed after the text is
marked up means editing `names.json`, `stress.txt` and every span. List the names that already exist and are
reused (with their current form) so the user sees the whole picture.

After approval:
- `assets/names.json`: `category`, a complete `localized` table (7 cases × 2 numbers), `translit` (a string if it doesn't decline) and `original` (only if it differs from the key). Keep the file's one-line-per-table format.
- `tts/stress.txt`: each form of two or more syllables on its own line with the stressed vowel in capitals (`зброЯр`, `зброярА`), under the `# Names` section. For a cape every form of the `localized` table; for a civilian name the forms the text uses.
- `assets/glossary.json`: a new civilian character gets a `characters` entry, a new `names` key a description that only tells what is known at `firstSeen`.
- A new speaking character: `tts/voices.json` with a short description (age, gender, manner of speech) and `"voiceName": null, "voiceId": null`; the user picks the voice later. One consistent English key per person.

## 5. Mark up the user's text

Change markup only. Don't reword the translation: report what looks wrong (a typo, a Latin letter, a name in a
form `names.json` doesn't have) and let the user decide.

```html
<div data-narrator="Taylor">
    <p>Narration with <span data-name="Lung" data-case="родовий">Луна</span> and <span data-character="Emma">Емма</span>.</p>
    <p><span data-voice="Brian">“Пряма мова,”</span> — сказав <span data-name="Grue">Морок</span>.</p>
    <p data-voice="Lisa">“Абзац, який повністю є реплікою.”</p>
</div>
```

- **One original paragraph is one `<p>`.** The voiceover chunks and text sync rely on paragraph boundaries. `fetch_original.py <id> --check` compares the counts; if they differ, find the merged or split paragraph with `orig/<id>.txt` and ask the user.
- `data-narrator`: whose voice reads the narration. Taylor for her chapters; for interludes the POV character, or `Reader` for neutral third person.
- `data-voice`: only on direct speech of someone other than the narrator. Wrap just the quoted words, the attribution stays with the narrator. A paragraph that is entirely one character's line gets `data-voice` on the `<p>`. The narrator's own lines need no markup.
- `data-name`: every cape name, team, organization or term that has an entry in `names.json`. The text inside is exactly the localized form, in the case the sentence needs (`data-case`; `data-form="множина"` for plural; both default to singular nominative). Choose the case from the sentence even when forms coincide.
- `data-character`: civilian names (Taylor, Emma, Danny…), styling only.
- Italics in the user's text stay `<i>`; nothing else: no `<br>`, no inline styles, no other attributes.

## 6. Check

```
python3 tools/fetch_original.py <id> --check   # paragraph count of the finished chapter against the original
python3 tools/markup_names.py <id> --write      # marks names you missed; prints the ones it couldn't decide
python3 tools/check_chapters.py --fix           # must end with 0 errors and 0 warnings
```

Mark the "need a case" leftovers by hand, review the "guessed" ones, then run the validator again.

## 7. Register and commit

- Add `{"id": "<id>", "textFile": "...", "status": "draft"}` to the arc in `assets/chapters.json`. No `audioFile` until the voiceover exists.
- Optionally preview with `python3 -m http.server 8000` and `http://localhost:8000/chapter_template.html?ch=<id>`.
- Commit as "Add raw <id> text" together with the names.json, stress.txt, glossary.json, voices.json and chapters.json changes. A push to `master` publishes the chapter, so push only when the user asks.

## 8. Report to the user

- New names with the forms used, new voices, a new arc title if any.
- What looked wrong in the text, and any paragraph-count mismatch.
