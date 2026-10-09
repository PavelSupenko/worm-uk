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

Before committing changes to chapters or names, run the markup validator (stdlib Python, no dependencies). It exits with code 1 on errors; `--fix` also rewrites the `firstSeen` values in `names.json`:

```
python3 tools/check_chapters.py [--fix]
```

The live site is served by GitHub Pages from `origin` (`PavelSupenko/worm-uk`, default branch `master`). Assume a push to `master` goes live.

## How the pages fit together

- `index.html` is the landing page ("continue reading" button, chapter list, author credits). `chapter_template.html` is the single reader page used for every chapter, selected by `?ch=<chapter id>`. Old links with `?major=<arc id>&sub=<chapter id>` still work (only `sub` is read).
- JavaScript is plain ES modules in `js/`, with no build step. `js/boot.js` is the only classic script: it runs in `<head>` and applies saved reading settings before first paint, exposing them as `window.WormSettings`. The entry points are `js/home.js` (index) and `js/reader.js` (chapter page). Shared modules: `data.js` (chapter list, titles, URLs), `toc.js` (table of contents), `settings.js` (settings drawer with the "Читання" and "Імена" tabs), `names.js` (name sets and replacement), `names-panel.js` (the "Імена" tab), `name-popover.js` (popover opened by clicking a name), `declension.js` (case guesses for a reader's own names), `progress.js` (last chapter, scroll and audio position), `storage.js` (guarded localStorage, keys prefixed `worm-uk:`), `ui.js` (icons, drawers). Icons are symbols in `assets/icons.svg`.
- `assets/chapters.json` is the table of contents. It lists arcs (`id`, `title`), and each arc lists chapters (`id`, `textFile`, optional `audioFile`, optional `status: "draft"` for unedited text, optional `title` to override the default "<arc title> <id>"). **A new chapter isn't reachable until it has an entry here.** Leave `audioFile` out until the recording exists; the page then shows a "voiceover in progress" note instead of a player. Prev/next links follow the order of this file, across arcs.
- Files are named by arc folder, `texts/<arc#>.<english-arc-name>/<id>.html` and `audio/<same folder>/<id>.mp3` (for example `texts/1.gestation/1.3.html`). Interludes use an `x` id (`1.x`).

## Chapter text markup

Chapter files are HTML fragments, not full documents. Each one is a single `<p id="chapter-text">` (the reader drops the duplicate id when injecting it) containing narrator blocks, and paragraphs are `<span>` elements separated by `<br><br>`:

```html
<p id="chapter-text">
    <span reader-name="Taylor">
        <span>Paragraph…</span>
        <br>
        <br>
        <span>Paragraph with <span character-name="Lung">Лун</span> and <span data-name="Grue" data-form="однина" data-case="родовий">Морока</span>.</span>
    </span>
</p>
```

The three name attributes do different things:

- **`reader-name="<English name>"`** marks who is narrating or speaking a block (`Reader` for author notes and neutral narration). Nothing reads it at runtime. It's there for later processing such as multi-voice audio.
- **`character-name="<English name>"`** is styling only (highlighted by CSS unless the reader turns highlighting off). Its Ukrainian text is written inline and is never replaced. Use it for civilian names (Taylor, Emma, Danny…) and for descriptions that stand in for a cape ("маска-череп").
- **`data-name="<key>"`** is for every name that has variants: capes, teams and organizations, terms. At runtime `applyNames()` in `js/names.js` replaces the span's text with the key's form in the reader's chosen name set, and the span becomes clickable (opens the name popover).
  - `data-form` must be `однина` or `множина`. `data-case` must be one of the seven Ukrainian case names (`називний`, `родовий`, `давальний`, `знахідний`, `орудний`, `місцевий`, `кличний`). Both default to the first value. Choose the case from the sentence even when the localized forms coincide (родовий and знахідний of `Лун` are both `Луна`): a reader's own name may decline differently.
  - **The text inside the span must be exactly the localized form** for that number and case. It is what readers see before the script runs and what the voiceover is generated from. A capital first letter at a sentence start is allowed and kept by the runtime.
  - Only the replaceable part goes inside the span: in `<span data-name="Ward">Вартові</span> Схід-Північ-Схід` the suffix, and quotes around a title, stay outside, or replacement would drop them.
  - A new key needs an entry in `assets/names.json`; the validator reports missing keys, wrong cases and names left without markup.

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

## Chapter workflow (from git history)

A chapter usually lands in stages, each as its own commit: raw translation ("Add raw/unedited X text"), then an edited text pass, then the audio voiceover plus its `audioFile` path in `chapters.json`. Converting names to `data-name` spans and adding them to `names.json` is sometimes postponed to a later commit; run the validator once they are in.
