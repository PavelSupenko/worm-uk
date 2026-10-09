// Small shared UI helpers: icons, dialogs, the auto-hiding top bar.
import { versioned } from './version.js';

export function icon(name) {
    return `<svg class="icon" aria-hidden="true"><use href="${versioned(`assets/icons.svg#${name}`)}"></use></svg>`;
}

export function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, ch => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[ch]);
}

// Wires a <dialog> used as a side drawer: closes on backdrop click and on
// any element marked with [data-close] inside it.
export function setupDrawer(dialog, openButton, onOpen) {
    openButton?.addEventListener('click', () => {
        dialog.showModal();
        onOpen?.();
    });
    dialog.addEventListener('click', event => {
        // The drawer body fills the dialog, so a click on the dialog itself is the backdrop
        if (event.target === dialog || event.target.closest('[data-close]')) dialog.close();
    });
    return dialog;
}

// Hides the top bar while scrolling down and shows it again on scroll up.
export function autoHideTopbar(topbar) {
    let lastY = window.scrollY;
    let ticking = false;
    window.addEventListener('scroll', () => {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
            const y = window.scrollY;
            if (y > lastY + 6 && y > 160) topbar.classList.add('topbar--hidden');
            else if (y < lastY - 6 || y <= 160) topbar.classList.remove('topbar--hidden');
            lastY = y;
            ticking = false;
        });
    }, { passive: true });
    // Keyboard users tabbing into the bar must be able to see it
    topbar.addEventListener('focusin', () => topbar.classList.remove('topbar--hidden'));
}
