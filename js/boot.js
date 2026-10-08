// Loaded as a classic blocking script in <head>: applies the saved reading
// settings before the first paint so the page never flashes the default theme.
// settings.js reuses these helpers through window.WormSettings.
(function () {
    var KEY = 'worm-uk:settings';
    var DEFAULTS = {
        theme: 'dark',        // dark | light | sepia
        font: 'serif',        // serif | sans
        size: 18,             // reader font size in px
        spacing: 'normal',    // compact | normal | relaxed
        highlightNames: true,
        audioRate: 1
    };

    function load() {
        var saved = null;
        try {
            saved = JSON.parse(localStorage.getItem(KEY));
        } catch (e) {
            // Storage can be blocked (private mode, disabled site data)
        }
        return Object.assign({}, DEFAULTS, saved || {});
    }

    function apply(settings) {
        var root = document.documentElement;
        root.dataset.theme = settings.theme;
        root.dataset.font = settings.font;
        root.dataset.spacing = settings.spacing;
        root.dataset.highlightNames = settings.highlightNames ? 'on' : 'off';
        root.style.setProperty('--reader-size', settings.size + 'px');
    }

    window.WormSettings = { KEY: KEY, DEFAULTS: DEFAULTS, load: load, apply: apply };
    apply(load());
})();
