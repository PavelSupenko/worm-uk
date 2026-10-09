# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Ukrainian translation of Wildbow's web serial *Worm*, published as a static site on GitHub Pages: https://pavelsupenko.github.io/worm-uk/. Each chapter has translated text and, once it's recorded, a voiceover MP3. UI strings and chapter text are in Ukrainian. Commit messages and code comments are in English.

## Running locally

There's no build step, package manager or test suite. The pages load their content with `fetch()`, so opening the HTML files over `file://` won't work. Serve the repo root instead:

```
python3 -m http.server 8000
# then open http://localhost:8000/ or e.g. http://localhost:8000/chapter_template.html?ch=1.5
```

The tools in `tools/` are stdlib Python 3.8+ with no dependencies (shared code in `tools/chapterlib.py`):

```
python3 tools/check_chapters.py [--fix]          # validate all chapters; --fix also updates firstSeen in names.json
python3 tools/markup_names.py <id> [--write]     # wrap unmarked names in data-name spans, case taken from the form
python3 tools/export_tts.py <id>                 # voiceover script for ElevenLabs -> tts/<id>.json
python3 tools/export_tts.py <id> --check tts/<id>.tagged.json
```

Run the validator before committing changes to chapters or names; it exits with code 1 on errors. Two project skills cover the content workflow: `.claude/skills/translate-chapter` (translate a new chapter straight into the markup) and `.claude/skills/tts-tags` (add ElevenLabs audio tags for the voiceover). `ROADMAP.md` tracks planned work.

The live site is GitHub Pages for `origin` (`PavelSupenko/worm-uk`, default branch `master`), deployed by `.github/workflows/pages.yml`: the validator runs first and the site only updates when it passes. `tools/build_site.sh` assembles the published files (pages, `js`, `assets`, `texts`, `audio`; tools, `tts` and docs are not published) and stamps the commit hash into module, stylesheet, icon and data URLs through `js/version.js`, so browsers never mix files from two deploys. Assume a push to `master` goes live within a few minutes.

## How the pages fit together

- `index.html` is the landing page ("continue reading" button, chapter list, author credits). `chapter_template.html` is the single reader page used for every chapter, selected by `?ch=<chapter id>`. Old links with `?major=<arc id>&sub=<chapter id>` still work (only `sub` is read).
- JavaScript is plain ES modules in `js/`, with no build step. `js/boot.js` is the only classic script: it runs in `<head>` and applies saved reading settings before first paint, exposing them as `window.WormSettings`. The entry points are `js/home.js` (index) and `js/reader.js` (chapter page). Shared modules: `data.js` (chapter list, titles, URLs), `toc.js` (table of contents), `settings.js` (settings drawer with the "Читання" and "Імена" tabs), `names.js` (name sets and replacement), `names-panel.js` (the "Імена" tab), `name-popover.js` (popover opened by clicking a name), `declension.js` (case guesses for a reader's own names), `typo-report.js` ("Повідомити про помилку": opens a GitHub issue quoting the selected text), `progress.js` (last chapter, scroll and audio position), `storage.js` (guarded localStorage, keys prefixed `worm-uk:`), `ui.js` (icons, drawers), `version.js` (deploy version for cache busting; `'dev'` locally). Import modules with plain relative paths (`from './names.js'`), which the deploy script rewrites. Icons are symbols in `assets/icons.svg`.
- `assets/chapters.json` is the table of contents. It lists arcs (`id`, `title`), and each arc lists chapters (`id`, `textFile`, optional `audioFile`, optional `status: "draft"` for unedited text, optional `title` to override the default "<arc title> <id>"). **A new chapter isn't reachable until it has an entry here.** Leave `audioFile` out until the recording exists; the page then shows a "voiceover in progress" note instead of a player. Prev/next links follow the order of this file, across arcs.
- Files are named by arc folder, `texts/<arc#>.<english-arc-name>/<id>.html` and `audio/<same folder>/<id>.mp3` (for example `texts/1.gestation/1.3.html`). Interludes use an `x` id (`1.x`).

## Chapter text markup

Chapter files are HTML fragments, not full documents, in a canonical format the tools read and write: one `<div data-narrator>` with one `<p>` per line.

```html
<div data-narrator="Taylor">
    <p>Narration with <span data-character="Emma">Емма</span> and <span data-name="Grue" data-case="родовий">Морока</span>.</p>
    <p><span data-voice="Brian">“Direct speech,”</span> — said <span data-name="Grue">Морок</span>.</p>
    <p data-voice="Reader">A paragraph entirely in another voice, e.g. an author's note.</p>
</div>
```

- **`data-narrator`** on the root is the voice of everything not marked otherwise: `Taylor` in her chapters, the POV character or `Reader` (neutral) in interludes.
- **`data-voice`** marks speech by someone other than the narrator: on a `<span>` around the quoted words (the attribution stays with the narrator), or on a `<p>` that is entirely that voice. Voices are keys of `tts/voices.json`. Nothing reads them at runtime; they drive the multi-voice voiceover.
- **`data-character="<English name>"`** is styling only (highlighted unless the reader turns highlighting off) and is never replaced. Use it for civilian names (Taylor, Emma, Danny…) and for descriptions that stand in for a cape ("маска-череп").
- **`data-name="<key>"`** is for every name that has variants: capes, teams and organizations, terms. At runtime `applyNames()` in `js/names.js` replaces the span's text with the key's form in the reader's chosen name set, and the span becomes clickable (opens the name popover).
  - `data-form` is `однина` (default) or `множина`; `data-case` is one of `називний` (default), `родовий`, `давальний`, `знахідний`, `орудний`, `місцевий`, `кличний`. Leave defaults out. Choose the case from the sentence even when the localized forms coincide (родовий and знахідний of `Лун` are both `Луна`): a reader's own name may decline differently.
  - **The text inside the span must be exactly the localized form** for that number and case. It is what readers see before the script runs and what the voiceover is generated from. A capital first letter at a sentence start is allowed and kept by the runtime.
  - Only the replaceable part goes inside the span: in `<span data-name="Ward">Вартові</span> Схід-Північ-Схід` the suffix, and quotes around a title, stay outside, or replacement would drop them.
  - A new key needs an entry in `assets/names.json`; the validator reports missing keys, wrong cases and names left without markup, and `tools/markup_names.py` adds most missing spans itself.
- One original paragraph is one `<p>`; keep it that way when editing, since voiceover chunks follow paragraph boundaries. No `<br>`, no other attributes.

## Name sets

`assets/names.json` has three parts: `sets` (`localized`, `translit`, `original`), `categories` (`cape`, `group`, `term`, used to group names in the settings) and `names`. Each name is keyed by its English name:

```json
"Grue": {
    "category": "cape",
    "localized": {"однина": {<7 cases>}, "множина": {<7 cases>}},
    "translit": "Ґрю",
    "original": "Grue",
    "firstSeen": "1.5"
}
```

- A value is either a full table or a plain string, which means indeclinable. A number can also be a single string (`"original": {"однина": "Ward", "множина": "Wards"}`).
- `localized` is required and must be complete. `translit` falls back to `localized`, `original` falls back to the key.
- `firstSeen` is the first chapter using the key. The settings hide names from chapters the reader hasn't opened yet, so the list doesn't spoil later capes. `tools/check_chapters.py --fix` maintains it.
- The validator writes `names.json` with one line per case table; keep that format when editing by hand.

The reader's choice lives in `localStorage["worm-uk:names"]` as `{ set, base, custom }`. `set` is one of the dictionary sets or `custom` ("Мої"); `custom` maps keys to the reader's own values (same format as above), and names without one come from `base`. Saving an own name switches to `custom` automatically. Readers change sets from the popover on a name or in the "Імена" tab of the settings, which also has the own-name editor and a JSON backup of the custom names. The voiceover always uses the localized names.

## Voiceover pipeline

Target: ElevenLabs Eleven v4 (`eleven_v4`, supports Ukrainian) through the Text to Dialogue API, where each request is a list of `{text, voice_id}` turns, about 2000 characters at most, and audio tags in square brackets direct the delivery.

1. `tools/export_tts.py <id>` turns the chapter into `tts/<id>.json`: chunks of whole paragraphs (under 1800 characters, leaving room for tags), each split into inputs by voice, with localized names. Not committed.
2. The `tts-tags` skill writes `tts/<id>.tagged.json` with audio tags added; `--check` guarantees the words are unchanged. Committed.
3. Not built yet: a sender that maps voices to `voiceId` from `tts/voices.json`, calls the API per chunk and joins the audio. Because chunks start at paragraph boundaries, the chunk start times give paragraph timings for text and audio sync.

## Chapter workflow (from git history)

A chapter usually lands in stages, each as its own commit: raw translation ("Add raw/unedited X text"), then an edited text pass, then the audio voiceover plus its `audioFile` path in `chapters.json`. Converting names to `data-name` spans and adding them to `names.json` is sometimes postponed to a later commit; run the validator once they are in.
