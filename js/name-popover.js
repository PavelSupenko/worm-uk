// Popover opened by clicking a name in the chapter: shows the name in every
// set, switches the set for the whole text, links to the reader's own variant.
// On narrow screens CSS turns it into a bottom sheet.
import { allSets, getNameState, nameValue, onNamesChange, pickForm, resolveName, setActiveSet } from './names.js';
import { escapeHtml, icon } from './ui.js';

const MOBILE = window.matchMedia('(max-width: 599px)');
const GAP = 8;

export function initNamePopover(root, { onCustomize }) {
    const popover = document.createElement('div');
    popover.className = 'name-popover';
    popover.popover = 'auto';
    popover.setAttribute('role', 'dialog');
    popover.setAttribute('aria-label', 'Варіанти імені');
    document.body.append(popover);
    let anchor = null;

    const open = element => {
        anchor = element;
        render();
        popover.showPopover();
        place();
        popover.querySelector('[aria-pressed="true"]')?.focus({ preventScroll: true });
    };

    const render = () => {
        const key = anchor.dataset.name;
        const { set } = getNameState();
        popover.innerHTML = `
            <div class="name-popover-head">
                <span class="name-popover-original">${escapeHtml(pickForm(nameValue(key, 'original')))}</span>
                <button class="icon-button" data-close aria-label="Закрити">${icon('close')}</button>
            </div>
            <p class="name-popover-caption">Набір імен для всього тексту</p>
            <div class="name-popover-sets">
                ${allSets().map(option => `
                    <button class="name-option" data-set="${option.id}" aria-pressed="${option.id === set}">
                        <span class="name-option-value">${escapeHtml(resolveName(key, anchor.dataset.form, anchor.dataset.case, option.id))}</span>
                        <span class="name-option-set">${escapeHtml(option.title)}</span>
                    </button>`).join('')}
            </div>
            <button class="button button--small button--ghost name-popover-customize" data-customize>Налаштувати своє ім'я…</button>`;
    };

    const place = () => {
        if (MOBILE.matches) {
            popover.style.removeProperty('top');
            popover.style.removeProperty('left');
            return;
        }
        // A name broken across lines has several boxes; anchor to the first one
        const box = anchor.getClientRects()[0] ?? anchor.getBoundingClientRect();
        const { offsetWidth: width, offsetHeight: height } = popover;
        let top = box.bottom + GAP;
        if (top + height > window.innerHeight - GAP) top = Math.max(GAP, box.top - height - GAP);
        const left = Math.min(Math.max(GAP, box.left + box.width / 2 - width / 2), window.innerWidth - width - GAP);
        popover.style.top = `${top}px`;
        popover.style.left = `${left}px`;
    };

    const isOpen = () => popover.matches(':popover-open');

    root.addEventListener('click', event => {
        const element = event.target.closest('[data-name]');
        if (element?.getAttribute('role') === 'button') open(element);
    });
    root.addEventListener('keydown', event => {
        if ((event.key === 'Enter' || event.key === ' ') && event.target.matches?.('[data-name][role="button"]')) {
            event.preventDefault();
            open(event.target);
        }
    });

    popover.addEventListener('click', event => {
        const option = event.target.closest('[data-set]');
        if (option) setActiveSet(option.dataset.set);
        if (event.target.closest('[data-close]')) popover.hidePopover();
        if (event.target.closest('[data-customize]')) {
            popover.hidePopover();
            onCustomize(anchor.dataset.name);
        }
    });
    popover.addEventListener('toggle', event => {
        // Return keyboard focus to the name it was opened from
        if (event.newState === 'closed' && popover.contains(document.activeElement)) {
            anchor?.focus({ preventScroll: true });
        }
    });

    // The set changed: refresh the highlighted option, keep the popover open
    onNamesChange(() => {
        if (!isOpen()) return;
        const focusedSet = document.activeElement?.dataset?.set;
        render();
        place();
        popover.querySelector(`[data-set="${focusedSet}"]`)?.focus({ preventScroll: true });
    });
    // On desktop the popover follows its name and closes once the name scrolls away
    window.addEventListener('scroll', () => {
        if (!isOpen() || MOBILE.matches) return;
        const box = anchor.getBoundingClientRect();
        if (box.bottom < 0 || box.top > window.innerHeight) popover.hidePopover();
        else place();
    }, { passive: true });
    window.addEventListener('resize', () => {
        if (isOpen()) place();
    });
}
