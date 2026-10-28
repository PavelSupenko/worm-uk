---
name: proofread-chapter
description: Editorial review of the user's Ukrainian translation of a Worm chapter - meaning checked against the original, Russianisms, calques from Russian and English, spelling, punctuation, cases and agreement, style - reported as a numbered list for the user to accept or reject, then the accepted fixes applied. Use when the user asks to proofread, edit, check or review a translated chapter or draft.
---

# Proofread a translated chapter

This is an editor's pass over the user's own translation: find what is wrong, propose the fix, let the user
decide. You don't translate. A suggestion is a word or a phrase, at most one sentence, in the user's own
wording; never rewrite a paragraph or the chapter from the original. Don't paste the original into the chat:
point to it by paragraph number and quote a few words at most.

## 1. What to read

- The text: the draft `orig/<id>.uk.txt` (best: fixes go in before the markup) or the chapter in `texts/` once
  it is registered. Paragraph numbers are the same in both and match the original.
- The original `orig/<id>.txt` for meaning. If it is missing: `python3 tools/fetch_original.py <id>`.
- `checklist.md` next to this file: what to look for, and the project conventions that are **not** errors.
- `docs/translation-brief.md`, section "Стиль", and the previous chapter in `texts/`: dialogue format,
  recurring terms, Taylor's voice.
- `assets/names.json` and `assets/glossary.json`: the names and terms already chosen. In a draft the capes,
  teams and terms stay in English without endings, so don't flag their case.

## 2. Mechanical pass

```
python3 tools/proofread.py <id>              # the registered chapter, or the draft if it isn't registered
python3 tools/proofread.py <id> --draft      # the draft orig/<id>.uk.txt even when the chapter exists
```

It lists Russian and Latin letters, quotes, apostrophes, dashes, ellipses, spaces, doubled words, the dialogue
format and common Russianisms. Lines without `?` are almost always errors; lines with `?` need your judgement
from the sentence. Drop the false ones, keep the rest for the report.

## 3. Reading pass

Read paragraph by paragraph with the original next to it and go through every section of `checklist.md`:
meaning, Russianisms, English calques, spelling, punctuation, cases and agreement, style and consistency.
For a long chapter (over about 120 paragraphs) work in parts of about 60 paragraphs and keep one running list,
so the end of the chapter gets the same attention as the start.

Be sure before calling something an error. Where the norm (правопис 2019, СУМ) allows both variants, it is not
an error: at most a style note marked "(на смак)". A word that only sounds Russian but is in modern Ukrainian
dictionaries is not a Russianism. Fewer, solid findings are worth more than a long list the user has to sift.

## 4. Report

In the chat language, the fragments in Ukrainian. One numbered list across the whole chapter, so the user
can answer "все, кроме 4 и 9", in three groups:

1. **Помилки**: meaning lost or changed, grammar, cases, agreement, spelling, punctuation, typography.
2. **Русизми і кальки**: with the usual Ukrainian replacement.
3. **Стиль**: suggestions only, mark matters of taste "(на смак)". Keep this group short.

One line per finding: paragraph number, a short quote of the user's text, the fix, and a few words why.

```
3. ¶12 «на протязі години» → «протягом години»: русизм
7. ¶20 «він кивнув своєю головою» → «він кивнув»: англійська калька, присвійний зайвий
11. ¶31 сказано, що батько чув її вночі, а в оригіналі він чув, як вона повернулася: зміст
```

End with the counts per group and say what you didn't check (for example: no original available).

## 5. Apply what the user accepts

- Only the findings the user accepted, exactly as agreed. Edit the draft or the chapter file in place.
- In a chapter file keep the markup: one paragraph stays one `<p>`, attributions stay outside `data-voice`
  spans, and a fix inside a `data-name` span changes its `data-case`/`data-form` together with the text (the
  text must stay the exact localized form).
- Then check: `python3 tools/fetch_original.py <id> --check-draft` for a draft (must end with `0 problems`),
  `python3 tools/check_chapters.py` for a chapter (0 errors, 0 warnings), and `tools/proofread.py` again.
- A chapter that already has `audioFile`: the recording keeps the old wording. Tell the user, and apply the
  same word changes to `tts/<id>.tagged.json` so `python3 tools/export_tts.py <id> --check tts/<id>.tagged.json`
  passes again; re-recording is the user's call.
- A draft in `orig/` is not committed. Fixes in `texts/` are committed as "Proofread <id>" with
  `git commit -- <paths>`.
