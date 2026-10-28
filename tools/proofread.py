#!/usr/bin/env python3
"""Mechanical proofreading of a translated chapter: the first pass of the
proofread-chapter skill, which reads the text for everything else.

Usage:
    python3 tools/proofread.py 2.1                 # the chapter in texts/ if it is registered, else orig/2.1.uk.txt
    python3 tools/proofread.py 2.1 --draft [PATH]  # the plain-text draft (default orig/2.1.uk.txt)

Reports, by paragraph number:
  - Russian letters (ы, э, ё, ъ) and Latin letters inside Cyrillic words
  - straight quotes and apostrophes, hyphens or en dashes used as a dash, "…" or
    two dots instead of "...", spaces before punctuation or missing after it,
    a doubled word
  - dialogue that breaks the project format: “…,” — сказала я
  - quotes left unclosed or closed without being opened
  - common Russianisms and calques with the usual Ukrainian replacement
Lines marked "?" need a judgement: the match is often fine ("так, як" compares,
"на рахунок" can be a bank account). Always exits 0: the findings are advice.
"""
import re
import sys

from chapterlib import ROOT, SPACES, chapter_root, find_chapter, load_chapters, read_chapter
from fetch_original import OUT_DIR, SCENE_BREAK, read_numbered

CONTEXT = 30
CYR = 'а-яА-ЯіїєґІЇЄҐ'
LETTER = f'A-Za-z{CYR}'
ADJECTIVE = '(?:ий|ого|ому|им|ім|а|ої|ій|у|ою|е|і|их|ими)'

# (pattern, message, certain): an uncertain match is printed with "?"
TYPOGRAPHY = [
    (r'[ыэёъЫЭЁЪ]', 'Russian letter', True),
    (rf'\w*(?:[A-Za-z][{CYR}]|[{CYR}][A-Za-z])\w*', 'Latin letter in a Cyrillic word', True),
    (r'"', 'straight quote: “…” for speech, «…» in narration', True),
    (rf"(?<=[{LETTER}])['ʼ`´](?=[{CYR}])", 'apostrophe: ’', True),
    (r'(?:^|(?<=\s))[-–](?=\s)|--', 'dash: —', True),
    (r'…', 'ellipsis: three dots ...', True),
    (r'\.{4,}|(?<![.?!])\.\.(?!\.)', 'ellipsis: three dots ...', True),
    (r'(?<=\S)  +', 'double space', True),
    (r' [,;:!?]| \.(?!\.)', 'space before punctuation', True),
    (rf'[,;:](?=[{LETTER}])|(?<=[a-zа-яіїєґ])[.!?](?=[A-ZА-ЯІЇЄҐ])|[”»](?=\w)|(?<=\w)[“«]',
     'missing space', True),
    (r'(?i)\b(\w+)\s+\1\b', 'doubled word (or a missing hyphen or comma)', True),
    (r'”,\s*—', 'the comma goes inside the quotes: “…,” —', True),
    (r'(?<![,?!.])”\s+—\s', 'a comma before the closing quote? “…,” —', False),
]

RUSSIANISMS = [
    (r'(?<![\w’\'ʼ])явля\w*с[яь]\b', 'бути, є (або з’являтися)', False),
    (r'\bна протязі\b', 'протягом, упродовж', True),
    (r'\bслідуюч\w*', 'наступний', True),
    (r'\bприй[мн]\w*\s+участ', 'брати участь', True),
    (r'\bспівпа[дс]\w*', 'збігатися', True),
    (r'\bполуч(?:а|и|у|ен)\w*', 'отримати, вийти', True),
    (r'\bпо крайній мірі\b', 'принаймні', True),
    (r'\bз тих пір\b', 'відтоді', True),
    (r'\bдо сих пір\b', 'досі', True),
    (r'\b[ву] кінці кінців\b', 'зрештою, врешті-решт', True),
    (r'\bприйшлос[ья]\b|\bприходиться\b|\bприходилос[ья]\b', 'довелося, доводиться', True),
    (r'\bбувш(?:ий|ого|ому|им|ім|а|ої|ій|у|ою|е|і|их|ими)\b', 'колишній', True),
    (r'\b[ву] (?:той же|те ж) час\b', 'водночас, тим часом', True),
    (r'\b[ву] залежності від\b', 'залежно від', True),
    (r'\bзгідно (?!з\b|із\b|зі\b)', 'згідно з', True),
    (r'\bзада\w*\s+(?:за)?питанн?\w*', 'ставити запитання', True),
    (r'\b(?:від|за)кри\w*\s+(?:\w+\s+)?двер', 'відчинити, зачинити двері', True),
    (r'\bнапротив\b', 'навпроти, навпаки', True),
    (r'\bлюб(?:ий|а|е|і|ого|ої|ому|ій|им|ими|их|у|ою)\s+(?:з|із|інш)', 'будь-який', True),
    (r'\bкажеться\b', 'здається', True),
    (r'\bсамочуття\b', 'самопочуття', True),
    (r'\bпопробу\w*', 'спробувати, покуштувати', True),
    (r'\bвдобавок\b', 'до того ж, на додачу', True),
    (r'\bна самому ділі\b|\b[ву] дійсності\b', 'насправді', True),
    (r'\bміроприєм\w*', 'захід', True),
    (rf'\b(?:оточуюч|бажаюч|відпочиваюч|початкуюч|завідуюч){ADJECTIVE}\b', 'навколишні, охочі, ті, хто…; початківець', True),
    (r'\b(?:краще|гірше|більше|менше),? чим\b', 'ніж, за', True),
    (r'\b[ву]\s+\d{1,2}[:.]\d{2}\b', 'о 6:28 (time takes «о»)', True),
    (r'\b[ву] першу чергу\b', 'насамперед, передусім', False),
    (r'\bна рахунок\b', 'щодо, стосовно (unless a bank account)', False),
    (r'\bтак як\b', 'бо, оскільки (when it gives a reason)', False),
    (r'\bвірно\b', 'правильно (when it means "correct")', False),
    (r'\bвибачаю(?:сь|ся)\b', 'перепрошую, вибач(те)', False),
    (r'\bпо-моєму\b', 'як на мене, на мою думку', False),
    (r'\bскуч(?:а|и)\w*', 'сумувати за, нудьгувати', False),
    (r'\bне дивлячись на\b', 'незважаючи на, попри (unless literally "not looking at")', False),
    (r'\bвиключенн\w*', 'виняток (when it means "exception")', False),
    (r'\bдякуючи\b', 'завдяки (when it means "thanks to")', False),
    (r'\bпідміт(?:ити|ив|ила|или|ило|иш|ить|ять|имо|ите)\b', 'помітити, зауважити', False),
    (r'\bвідміт(?:ити|ив|ила|или|ило|ить|ять|имо)\b|\bвідміча\w*','зазначити, позначити, відзначити', False),
    (r'\bпоступ(?:ати|аю|аєш|ає|ають|ав|ала|али|ив|ила|или)\b', 'вчинити, вступити, надходити', False),
    (r'\bдавай(?:те)?\s+\w+т(?:и|ись|ися)\b', 'ходімо, зробімо (imperative instead of давай + infinitive)', False),
    (rf'\bсам(?!е\b){ADJECTIVE}\s+(?!перш)\w+[шщ]{ADJECTIVE}\b', 'най- (superlative)', False),
]

CHECKS = [(re.compile(p, re.IGNORECASE if i >= len(TYPOGRAPHY) else 0), m, c)
          for i, (p, m, c) in enumerate(TYPOGRAPHY + RUSSIANISMS)]


def draft_paragraphs(path):
    items, problems = read_numbered(path)
    for problem in problems:
        print(f'  {problem}')
    for number, text in items:
        if number != SCENE_BREAK:
            yield number, re.sub(r'</?[ib]>', '', text).replace('⏎', ' ')


def chapter_paragraphs(chapter):
    root = chapter_root(read_chapter(chapter))
    if root is None:
        raise SystemExit(f'{chapter["textFile"]}: not a chapter (run tools/check_chapters.py)')
    paragraphs = [p for p in root.elements() if p.tag == 'p']
    for number, paragraph in enumerate(paragraphs, 1):
        yield number, SPACES.sub(' ', paragraph.text()).strip()


def excerpt(text, start, end):
    left = text[max(0, start - CONTEXT):start]
    right = text[end:end + CONTEXT]
    return (('…' if start > CONTEXT else '') + left + '[' + text[start:end] + ']' + right
            + ('…' if end + CONTEXT < len(text) else ''))


def check_paragraph(text, next_text):
    findings = []
    for pattern, message, certain in CHECKS:
        for match in pattern.finditer(text):
            findings.append((match.start(), certain, excerpt(text, match.start(), match.end()), message))
    for opening, closing in (('“', '”'), ('«', '»')):
        # Speech that goes on in the next paragraph stays open: the next one starts with “ again
        if text.count(opening) > text.count(closing) and not next_text.startswith(opening):
            findings.append((text.index(opening), True, '', f'{opening} not closed'))
        elif text.count(closing) > text.count(opening):
            findings.append((text.index(closing), True, '', f'{closing} without an opening {opening}'))
    return sorted(findings)


def main(args):
    if '-h' in args or '--help' in args or not args:
        print(__doc__)
        return 0
    chapter_id = args[0]
    registered = {c['id']: c for c in load_chapters()}
    if '--draft' in args or chapter_id not in registered:
        rest = args[args.index('--draft') + 1:] if '--draft' in args else []
        path = ROOT / rest[0] if rest else OUT_DIR / f'{chapter_id}.uk.txt'
        if not path.is_file():
            raise SystemExit(f'No draft {path.relative_to(ROOT)} and {chapter_id} is not in chapters.json')
        source, paragraphs = path.relative_to(ROOT), draft_paragraphs(path)
    else:
        chapter = registered[chapter_id]
        source, paragraphs = chapter['textFile'], chapter_paragraphs(chapter)
    print(f'{chapter_id} ({source})')
    paragraphs = list(paragraphs)
    total = unsure = 0
    for index, (number, text) in enumerate(paragraphs):
        next_text = paragraphs[index + 1][1] if index + 1 < len(paragraphs) else ''
        for _, certain, context, message in check_paragraph(text, next_text):
            total += 1
            unsure += not certain
            print(f'{number:>4}{" " if certain else "?"} {message}' + (f': {context}' if context else ''))
    print(f'{total} findings, {unsure} of them marked ? need a judgement')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
