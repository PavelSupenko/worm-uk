// "Повідомити про помилку": selecting text in the chapter shows a button that
// opens a GitHub issue with the chapter and the quoted fragment.
import { getNameState } from './names.js';
import { escapeHtml } from './ui.js';

const ISSUES_URL = 'https://github.com/PavelSupenko/worm-uk/issues/new';
const MAX_QUOTE = 500;
// Mobile browsers collapse the selection when the button is tapped, so the
// button lingers briefly and remembers the last selected text
const HIDE_DELAY = 400;

export function initTypoReport(article, footer, { title, url }) {
    const button = document.createElement('button');
    button.className = 'button typo-button';
    button.hidden = true;
    button.textContent = 'Повідомити про помилку';
    document.body.append(button);
    let quote = '';
    let hideTimer = null;

    document.addEventListener('selectionchange', () => {
        const selection = document.getSelection();
        const text = selection.toString().trim();
        const inside = selection.rangeCount && article.contains(selection.getRangeAt(0).commonAncestorContainer);
        if (text && inside) {
            clearTimeout(hideTimer);
            quote = text;
            button.hidden = false;
        } else if (!button.hidden) {
            clearTimeout(hideTimer);
            hideTimer = setTimeout(() => { button.hidden = true; }, HIDE_DELAY);
        }
    });
    // Keep the selection when the button is pressed with a mouse
    button.addEventListener('mousedown', event => event.preventDefault());
    button.addEventListener('click', () => {
        window.open(issueUrl(title, url, quote), '_blank', 'noopener');
        button.hidden = true;
    });

    footer.innerHTML = `Знайшли помилку? Виділіть фрагмент тексту або <a href="${escapeHtml(issueUrl(title, url))}" target="_blank" rel="noopener">напишіть про неї</a>.`;
}

function issueUrl(title, url, quote = '') {
    const lines = [`**Глава:** ${title} (${url})`];
    // The reader sees names from their chosen set; say so, the translator works with the localized ones
    const { set } = getNameState();
    if (set !== 'localized') lines.push(`**Набір імен:** ${set}`);
    if (quote) {
        const shortened = quote.length > MAX_QUOTE ? `${quote.slice(0, MAX_QUOTE)}…` : quote;
        lines.push('', '**Фрагмент:**', ...shortened.split('\n').map(line => `> ${line}`));
    }
    lines.push('', '**Що не так і як краще:**', '');
    const params = new URLSearchParams({ title: `Помилка: ${title}`, body: lines.join('\n') });
    return `${ISSUES_URL}?${params}`;
}
