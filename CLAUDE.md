# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Ukrainian translation of Wildbow's web serial *Worm*, published as a static site on GitHub Pages: https://pavelsupenko.github.io/worm-uk/. Each chapter has translated text and, once it's recorded, a voiceover MP3. UI strings and chapter text are in Ukrainian. Commit messages and new code comments are in English, even though the existing comments in `script.js` are in Ukrainian.

## Running locally

There's no build step, package manager, linter, or test suite. The pages load their content with `fetch()`, so opening the HTML files over `file://` won't work. Serve the repo root instead:

```
python3 -m http.server 8000
# then open http://localhost:8000/ or e.g. http://localhost:8000/chapter_template.html?major=1&sub=1.5
```

The live site is served by GitHub Pages from `origin` (`PavelSupenko/worm-uk`, default branch `master`). Assume a push to `master` goes live.

## How the pages fit together

- `index.html` is the landing page (author credits and chapter list). `chapter_template.html` is the single reader page used for every chapter, selected by the query parameters `?major=<arc id>&sub=<chapter id>`. Both pages load the same `script.js`.
- `assets/chapters.json` is the table of contents. It lists arcs (`id`, `title`), and each arc lists chapters (`id`, `textFile`, `audioFile`). `script.js` builds the chapter list from it on both pages, then `loadChapter()` finds the chapter named in the URL, injects its `textFile` into `#chapter-text`, and adds an `<audio>` player for `audioFile`. **A new chapter isn't reachable until it has an entry here.** Chapters without a recording currently point `audioFile` at `1.4.mp3` as a placeholder.
- Files are named by arc folder, `texts/<arc#>.<english-arc-name>/<id>.html` and `audio/<same folder>/<id>.mp3` (for example `texts/1.gestation/1.3.html`). Interludes use an `x` id (`1.x`).

## Chapter text markup

Chapter files are HTML fragments, not full documents. Each one is a single `<p id="chapter-text">` containing narrator blocks, and paragraphs are `<span>` elements separated by `<br><br>`:

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
- **`character-name="<English name>"`** is styling only (highlighted by CSS). Its Ukrainian text is written inline and is never replaced.
- **`data-name="<key>"`** gets replaced at runtime. `replaceNamesInText()` overwrites the span's text with `names[key][data-form][data-case]` from `assets/translations.json`, so whatever Ukrainian text you write inside the span is only a fallback for the moment before the script runs.
  - `data-form` must be `однина` or `множина`. `data-case` must be one of the seven Ukrainian case names (`називний`, `родовий`, `давальний`, `знахідний`, `орудний`, `місцевий`, `кличний`). Both default to the first value (`однина` and `називний`).
  - **If the key, form, or case is missing from `translations.json`, the span shows the raw English key.** Whenever you add a `data-name` span, add the matching entry (all 7 cases × 2 numbers) to `translations.json`.

## Name translations

`assets/translations.json` maps each English key to its full declension: `{ "<key>": { "однина": {<7 cases>}, "множина": {<7 cases>} } }`. In the browser, `script.js` merges any reader overrides from `localStorage.customNames` over these defaults, with the reader's values winning. The "Редагувати імена" button is a raw JSON `prompt()` that edits those overrides. Because of this, a reader with saved overrides won't see changes to the defaults for the keys they've overridden.

## Chapter workflow (from git history)

A chapter usually lands in stages, each as its own commit: raw translation ("Add raw/unedited X text"), then an edited text pass, then the audio voiceover plus its `audioFile` path in `chapters.json`. Converting names to `data-name` spans and adding their translations is sometimes postponed to a later commit.
