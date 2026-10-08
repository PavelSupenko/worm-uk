# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Ukrainian translation of Wildbow's web serial *Worm*, published as a static site on GitHub Pages: https://pavelsupenko.github.io/worm-uk/. Each chapter has translated text and, once it's recorded, a voiceover MP3. UI strings and chapter text are in Ukrainian. Commit messages and code comments are in English.

## Running locally

There's no build step, package manager, linter, or test suite. The pages load their content with `fetch()`, so opening the HTML files over `file://` won't work. Serve the repo root instead:

```
python3 -m http.server 8000
# then open http://localhost:8000/ or e.g. http://localhost:8000/chapter_template.html?ch=1.5
```

The live site is served by GitHub Pages from `origin` (`PavelSupenko/worm-uk`, default branch `master`). Assume a push to `master` goes live.

## How the pages fit together

- `index.html` is the landing page ("continue reading" button, chapter list, author credits). `chapter_template.html` is the single reader page used for every chapter, selected by `?ch=<chapter id>`. Old links with `?major=<arc id>&sub=<chapter id>` still work (only `sub` is read).
- JavaScript is plain ES modules in `js/`, with no build step. `js/boot.js` is the only classic script: it runs in `<head>` and applies saved reading settings before first paint, exposing them as `window.WormSettings`. The entry points are `js/home.js` (index) and `js/reader.js` (chapter page). Shared modules: `data.js` (chapter list, titles, URLs), `toc.js` (table of contents), `settings.js` (settings drawer), `names.js` (name replacement), `progress.js` (last chapter, scroll and audio position), `storage.js` (guarded localStorage, keys prefixed `worm-uk:`), `ui.js` (icons, drawers). Icons are symbols in `assets/icons.svg`.
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
- **`character-name="<English name>"`** is styling only (highlighted by CSS unless the reader turns highlighting off). Its Ukrainian text is written inline and is never replaced.
- **`data-name="<key>"`** gets replaced at runtime. `applyNames()` in `js/names.js` overwrites the span's text with `names[key][data-form][data-case]` from `assets/translations.json`. The Ukrainian text you write inside the span is the fallback, and it should be the exact same form, since the voiceover is generated from it.
  - `data-form` must be `однина` or `множина`. `data-case` must be one of the seven Ukrainian case names (`називний`, `родовий`, `давальний`, `знахідний`, `орудний`, `місцевий`, `кличний`). Both default to the first value (`однина` and `називний`).
  - If the form or case is missing, the nominative is used; if the key is missing, the inline fallback text stays. Still, whenever you add a `data-name` span, add the matching entry (all 7 cases × 2 numbers) to `translations.json`.
  - Only the replaceable part goes inside the span: in `<span data-name="Ward">Вартові</span> Схід-Північ-Схід` the suffix stays outside, or replacement would drop it.

## Name translations

`assets/translations.json` maps each English key to its full declension: `{ "<key>": { "однина": {<7 cases>}, "множина": {<7 cases>} } }`. In the browser, `js/names.js` merges reader overrides from `localStorage.customNames` over these defaults, case by case. Only values that differ from the defaults are stored, so changes to the defaults still reach readers except for the exact forms they overrode. The override editor is currently a temporary raw-JSON textarea in the settings drawer; it is due to be replaced by name sets (localized / transliterated / original / reader's own).

## Chapter workflow (from git history)

A chapter usually lands in stages, each as its own commit: raw translation ("Add raw/unedited X text"), then an edited text pass, then the audio voiceover plus its `audioFile` path in `chapters.json`. Converting names to `data-name` spans and adding their translations is sometimes postponed to a later commit.
